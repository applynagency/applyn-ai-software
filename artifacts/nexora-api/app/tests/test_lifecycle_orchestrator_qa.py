"""Lifecycle orchestrator QA chain auto-resolution tests."""

from unittest.mock import AsyncMock, patch

from app.lifecycle.impact import QA_AGENT_CHAIN
from app.lifecycle.prerequisites import chain_prefix_for_agents
from app.schemas.deployment import DeploymentRunResponse
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
)


def test_chain_prefix_for_assembly_includes_qa_chain():
    chain = chain_prefix_for_agents(["fullstack_assembly"])
    assert "qa_architect" in chain
    assert "unit_test_generator" in chain
    assert "integration_test" in chain
    assert "security_test" in chain
    assert "performance_test" in chain
    assert "qa_approval" in chain
    qa_indices = [chain.index(agent) for agent in QA_AGENT_CHAIN]
    assert qa_indices == sorted(qa_indices)
    assert chain.index("qa_approval") < chain.index("fullstack_assembly")


async def test_assembly_orchestrator_dispatches_qa_agents(client):
    _, tokens = await create_authenticated_user(
        client, email="orch-qa-asm@example.com", username="orchqaasm"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="orch-qa-asm-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="orch-qa-asm-pr"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )

    dispatched: list[str] = []

    async def _fake_dispatch(*, internal_agent, requirement_content, session, requirement_id, user):
        dispatched.append(internal_agent)
        return type(
            "DispatchResult",
            (),
            {
                "status": "completed",
                "output": {"id": f"{internal_agent}-run", "qa_status": "QA_APPROVED"},
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
            "app.lifecycle.orchestrator.AgentPrerequisiteChecker.is_satisfied",
            new=AsyncMock(return_value=False),
        ),
    ):
        from app.lifecycle.orchestrator import LifecycleOrchestratorService
        from app.tests.test_dispatcher_coverage_sprint import _dispatcher_user

        session, user = await _dispatcher_user(client, tokens)
        orchestrator = LifecycleOrchestratorService(session)
        await orchestrator.ensure_assembly_prerequisites(
            requirement_id=requirement["id"],
            requirement_content=requirement["content"],
            user=user,
        )

    for agent in QA_AGENT_CHAIN:
        assert agent in dispatched


async def test_deploy_orchestrator_includes_qa_chain(client):
    _, tokens = await create_authenticated_user(
        client, email="orch-qa-dep@example.com", username="orchqadep"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="orch-qa-dep-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="orch-qa-dep-pr"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )

    dispatched: list[str] = []

    async def _fake_dispatch(*, internal_agent, requirement_content, session, requirement_id, user):
        dispatched.append(internal_agent)
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
            "app.lifecycle.orchestrator.AgentPrerequisiteChecker.is_satisfied",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "app.lifecycle.orchestrator.AgentPrerequisiteChecker.has_approved_approval",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.lifecycle.orchestrator.AgentPrerequisiteChecker.has_approved_qa_approval",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.services.deployment.DeploymentService.run",
            new=AsyncMock(
                return_value=DeploymentRunResponse(
                    id="dep-qa-1",
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
    for agent in QA_AGENT_CHAIN:
        assert agent in dispatched
