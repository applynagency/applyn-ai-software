from unittest.mock import AsyncMock, patch

from app.lifecycle.customer_messages import translate_customer_error
from app.lifecycle.prerequisites import chain_prefix_for_agents
from app.schemas.deployment import DeploymentRunResponse
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
)


def test_translate_customer_error_hides_internal_agent_names():
    assert (
        translate_customer_error("No completed Full Stack Assembly run found. Run Full Stack Assembly first.")
        == "Preparing deployment package..."
    )
    assert (
        translate_customer_error("Missing Business Analyst run")
        == "Application build is still in progress."
    )
    assert (
        translate_customer_error("Frontend Execution required")
        == "Finishing validation checks."
    )


def test_prerequisites_for_agents_excludes_planned_regeneration_agents():
    from app.lifecycle.impact import BACKEND_AGENT_CHAIN, FRONTEND_AGENT_CHAIN, QA_AGENT_CHAIN
    from app.lifecycle.prerequisites import FOUNDATION_CHAIN, prerequisites_for_agents

    targets = FRONTEND_AGENT_CHAIN + ["fullstack_assembly", "approval", "deployment"]
    prereqs = prerequisites_for_agents(targets)
    assert prereqs == FOUNDATION_CHAIN + BACKEND_AGENT_CHAIN + QA_AGENT_CHAIN
    assert "uiux_designer" not in prereqs
    assert "deployment" not in prereqs


def test_chain_prefix_for_agents_includes_finalization_prerequisites():
    from app.lifecycle.impact import QA_AGENT_CHAIN

    chain = chain_prefix_for_agents(["deployment"])
    assert "product_owner" in chain
    assert "backend_execution" in chain
    assert "frontend_execution" in chain
    for agent in QA_AGENT_CHAIN:
        assert agent in chain
    assert "fullstack_assembly" in chain
    assert "approval" in chain
    assert chain[-1] == "deployment"


async def test_deploy_without_pipeline_auto_resolves_prerequisites(client):
    _, tokens = await create_authenticated_user(
        client, email="orch-deploy@example.com", username="orchdeploy"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="orch-deploy-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="orch-deploy-pr"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )

    async def _fake_dispatch(*, internal_agent, requirement_content, session, requirement_id, user):
        return type(
            "DispatchResult",
            (),
            {
                "status": "completed",
                "output": {"id": f"{internal_agent}-run"},
                "log_messages": [],
                "error_message": None,
            },
        )()

    with (
        patch(
            "app.lifecycle.orchestrator.AgentDispatcher.dispatch_internal",
            new=AsyncMock(side_effect=_fake_dispatch),
        ),
        patch(
            "app.lifecycle.orchestrator.AgentPrerequisiteChecker.has_approved_qa_approval",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.services.deployment.DeploymentService.run",
            new=AsyncMock(
                return_value=DeploymentRunResponse(
                    id="dep-orch-1",
                    organization_id="org-1",
                    project_id=project["id"],
                    requirement_id=requirement["id"],
                    approval_run_id="appr-1",
                    fullstack_assembly_run_id="fsa-1",
                    status="DEPLOYED",
                    deployment_provider="AZURE",
                    live_url="https://app.example.com",
                    environment="production",
                    rollback_available=False,
                    created_by="user-1",
                    created_at="2026-01-01T00:00:00Z",
                    completed_at="2026-01-01T00:00:00Z",
                    error_message=None,
                    validation_score=100.0,
                    deployer_version="v1",
                    artifact=None,
                )
            ),
        ),
    ):
        response = await client.post(
            "/v1/agents/deployment/run",
            headers=auth_headers(tokens["access_token"]),
            json={"requirement_id": requirement["id"]},
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["customer_message"] == "Deployment started..."
    assert "Business Analyst" not in response.text
    assert "Full Stack Assembly" not in response.text


async def test_regeneration_without_pipeline_auto_resolves_prerequisites(client):
    _, tokens = await create_authenticated_user(
        client, email="orch-regen@example.com", username="orchregen"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="orch-regen-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="orch-regen-pr"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    created = await client.post(
        "/v1/change-requests",
        headers=auth_headers(tokens["access_token"]),
        json={
            "requirement_id": requirement["id"],
            "title": "Dashboard refresh",
            "description": "ui component update",
            "scope": "FRONTEND_ONLY",
        },
    )
    assert created.status_code == 201
    run_id = created.json()["id"]

    async def _fake_dispatch(*, internal_agent, requirement_content, session, requirement_id, user):
        return type(
            "DispatchResult",
            (),
            {
                "status": "completed",
                "output": {"id": f"{internal_agent}-run", "live_url": "https://app.example.com"},
                "log_messages": [],
                "error_message": None,
            },
        )()

    with patch(
        "app.lifecycle.orchestrator.AgentDispatcher.dispatch_internal",
        new=AsyncMock(side_effect=_fake_dispatch),
    ):
        response = await client.post(
            "/v1/regeneration",
            headers=auth_headers(tokens["access_token"]),
            json={"regeneration_run_id": run_id},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["customer_message"].startswith("Version regeneration")
    assert "business_analyst" not in response.text.lower()


async def test_customer_journey_no_prerequisite_errors(client):
    """Register through release without 422 or internal agent terminology."""
    _, tokens = await create_authenticated_user(
        client, email="orch-journey@example.com", username="orchjourney"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="orch-journey-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="orch-journey-pr"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )

    async def _fake_dispatch(*, internal_agent, requirement_content, session, requirement_id, user):
        return type(
            "DispatchResult",
            (),
            {
                "status": "completed",
                "output": {
                    "id": f"{internal_agent}-run",
                    "live_url": "https://app.example.com",
                    "approval_status": "UNDER_REVIEW",
                },
                "log_messages": [],
                "error_message": None,
            },
        )()

    internal_terms = (
        "business analyst",
        "backend architect",
        "frontend execution",
        "full stack assembly",
        "approval workflow",
        "dispatcher",
        "workflow engine",
    )

    with (
        patch(
            "app.lifecycle.orchestrator.AgentDispatcher.dispatch_internal",
            new=AsyncMock(side_effect=_fake_dispatch),
        ),
        patch(
            "app.lifecycle.orchestrator.AgentPrerequisiteChecker.has_approved_qa_approval",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.services.deployment.DeploymentService.run",
            new=AsyncMock(
                return_value=DeploymentRunResponse(
                    id="dep-journey-1",
                    organization_id="org-1",
                    project_id=project["id"],
                    requirement_id=requirement["id"],
                    approval_run_id="appr-1",
                    fullstack_assembly_run_id="fsa-1",
                    status="DEPLOYED",
                    deployment_provider="AZURE",
                    live_url="https://app.example.com",
                    environment="production",
                    rollback_available=False,
                    created_by="user-1",
                    created_at="2026-01-01T00:00:00Z",
                    completed_at="2026-01-01T00:00:00Z",
                    error_message=None,
                    validation_score=100.0,
                    deployer_version="v1",
                    artifact=None,
                )
            ),
        ),
    ):
        deploy = await client.post(
            "/v1/agents/deployment/run",
            headers=auth_headers(tokens["access_token"]),
            json={"requirement_id": requirement["id"]},
        )
        assert deploy.status_code == 201, deploy.text
        assert not any(term in deploy.text.lower() for term in internal_terms)

        change = await client.post(
            "/v1/change-requests",
            headers=auth_headers(tokens["access_token"]),
            json={
                "requirement_id": requirement["id"],
                "title": "Add export button",
                "description": "ui export feature",
                "scope": "FRONTEND_ONLY",
            },
        )
        assert change.status_code == 201, change.text
        run_id = change.json()["id"]

        regen = await client.post(
            "/v1/regeneration",
            headers=auth_headers(tokens["access_token"]),
            json={"regeneration_run_id": run_id},
        )
        assert regen.status_code == 200, regen.text
        assert not any(term in regen.text.lower() for term in internal_terms)

        release = await client.post(
            "/v1/releases",
            headers=auth_headers(tokens["access_token"]),
            json={
                "requirement_id": requirement["id"],
                "title": "Patch release",
                "description": "api bug fix",
                "scope": "BACKEND_ONLY",
            },
        )
        assert release.status_code == 201, release.text
        assert release.json()["customer_message"].startswith("Release v")


async def test_create_release_endpoint_returns_customer_message(client):
    _, tokens = await create_authenticated_user(
        client, email="orch-release@example.com", username="orchrelease"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="orch-rel-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="orch-rel-pr"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )

    async def _fake_dispatch(*, internal_agent, requirement_content, session, requirement_id, user):
        return type(
            "DispatchResult",
            (),
            {
                "status": "completed",
                "output": {"id": f"{internal_agent}-run", "live_url": "https://app.example.com"},
                "log_messages": [],
                "error_message": None,
            },
        )()

    with patch(
        "app.lifecycle.orchestrator.AgentDispatcher.dispatch_internal",
        new=AsyncMock(side_effect=_fake_dispatch),
    ):
        response = await client.post(
            "/v1/releases",
            headers=auth_headers(tokens["access_token"]),
            json={
                "requirement_id": requirement["id"],
                "title": "Bug fix",
                "description": "api bug fix",
                "scope": "BACKEND_ONLY",
            },
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["customer_message"].startswith("Release v")
    assert "in progress" in body["customer_message"]
