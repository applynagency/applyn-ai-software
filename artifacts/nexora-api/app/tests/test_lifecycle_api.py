from unittest.mock import AsyncMock, patch

from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    setup_deployment_pipeline,
)


async def _seed_context(client, token: str, suffix: str):
    workspace = await create_workspace(client, token, slug=f"lc-{suffix}-ws")
    project = await create_project(client, token, workspace_id=workspace["id"], slug=f"lc-{suffix}-pr")
    requirement = await create_requirement(client, token, project_id=project["id"])
    return workspace, project, requirement


async def test_create_change_request(client):
    _, tokens = await create_authenticated_user(client, email="lc-create@example.com", username="lccreate")
    _, _, requirement = await _seed_context(client, tokens["access_token"], "create")
    response = await client.post(
        "/v1/change-requests",
        headers=auth_headers(tokens["access_token"]),
        json={
            "requirement_id": requirement["id"],
            "title": "CRM dashboard enhancement",
            "description": "Update reports and KPI cards",
            "scope": "FRONTEND_ONLY",
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "PENDING"
    assert data["scope"] == "FRONTEND_ONLY"
    assert data["target_version"].startswith("v")


async def test_list_change_requests(client):
    _, tokens = await create_authenticated_user(client, email="lc-list@example.com", username="lclist")
    _, _, requirement = await _seed_context(client, tokens["access_token"], "list")
    for idx in range(2):
        response = await client.post(
            "/v1/change-requests",
            headers=auth_headers(tokens["access_token"]),
            json={
                "requirement_id": requirement["id"],
                "title": f"Change {idx}",
                "description": "Backend API update",
                "scope": "BACKEND_ONLY",
            },
        )
        assert response.status_code == 201
    listed = await client.get(
        "/v1/change-requests",
        headers=auth_headers(tokens["access_token"]),
        params={"requirement_id": requirement["id"]},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] >= 2


async def test_list_change_requests_org_wide(client):
    _, tokens = await create_authenticated_user(client, email="lc-org@example.com", username="lcorg")
    _, _, requirement = await _seed_context(client, tokens["access_token"], "org")
    created = await client.post(
        "/v1/change-requests",
        headers=auth_headers(tokens["access_token"]),
        json={
            "requirement_id": requirement["id"],
            "title": "Org-wide list test",
            "description": "Verify optional requirement filter",
            "scope": "FULL_STACK",
        },
    )
    assert created.status_code == 201
    listed = await client.get(
        "/v1/change-requests",
        headers=auth_headers(tokens["access_token"]),
        params={"offset": 0, "limit": 50},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1


async def test_change_request_submit_and_decide(client):
    _, tokens = await create_authenticated_user(client, email="lc-flow@example.com", username="lcflow")
    _, _, requirement = await _seed_context(client, tokens["access_token"], "flow")
    created = await client.post(
        "/v1/change-requests",
        headers=auth_headers(tokens["access_token"]),
        json={
            "requirement_id": requirement["id"],
            "title": "Approval workflow test",
            "description": "Submit and approve change request",
            "scope": "BACKEND_ONLY",
        },
    )
    assert created.status_code == 201
    run_id = created.json()["id"]
    assert created.json()["approval_status"] == "DRAFT"

    submit = await client.post(
        f"/v1/change-requests/{run_id}/submit",
        headers=auth_headers(tokens["access_token"]),
    )
    assert submit.status_code == 200
    assert submit.json()["approval_status"] == "SUBMITTED"

    decide = await client.post(
        f"/v1/change-requests/{run_id}/decide",
        headers=auth_headers(tokens["access_token"]),
        json={"approved": True, "comment": "Looks good"},
    )
    assert decide.status_code == 200
    assert decide.json()["approval_status"] == "APPROVED"
    assert decide.json()["approval_comment"] == "Looks good"


async def test_recompute_impact_analysis(client):
    _, tokens = await create_authenticated_user(client, email="lc-impact@example.com", username="lcimpact")
    _, _, requirement = await _seed_context(client, tokens["access_token"], "impact")
    created = await client.post(
        "/v1/change-requests",
        headers=auth_headers(tokens["access_token"]),
        json={
            "requirement_id": requirement["id"],
            "title": "Data model update",
            "description": "database model endpoint migration",
            "scope": "BACKEND_ONLY",
        },
    )
    run_id = created.json()["id"]
    updated = await client.post(
        "/v1/impact-analysis",
        headers=auth_headers(tokens["access_token"]),
        json={"regeneration_run_id": run_id},
    )
    assert updated.status_code == 200
    assert updated.json()["impact_analysis"]["risk_score"] >= 20


async def test_execute_regeneration_runs_only_planned_agents(client):
    _, tokens = await create_authenticated_user(client, email="lc-exec@example.com", username="lcexec")
    _, _, requirement = await _seed_context(client, tokens["access_token"], "exec")
    # Seed historical pipeline so prerequisite lookups exist.
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await client.post(
        "/v1/change-requests",
        headers=auth_headers(tokens["access_token"]),
        json={
            "requirement_id": requirement["id"],
            "title": "Frontend layout refresh",
            "description": "ui dashboard component update",
            "scope": "FRONTEND_ONLY",
        },
    )
    run_id = created.json()["id"]

    calls = []

    async def _fake_dispatch(*, internal_agent, requirement_content, session, requirement_id, user):
        calls.append(internal_agent)
        return type(
            "DispatchResult",
            (),
            {
                "status": "completed",
                "output": {"id": f"{internal_agent}-run-id"},
                "log_messages": [],
                "error_message": None,
            },
        )()

    with patch("app.services.lifecycle.AgentDispatcher.dispatch_internal", new=AsyncMock(side_effect=_fake_dispatch)):
        executed = await client.post(
            "/v1/regeneration",
            headers=auth_headers(tokens["access_token"]),
            json={"regeneration_run_id": run_id},
        )
    assert executed.status_code == 200, executed.text
    data = executed.json()
    assert data["status"] == "COMPLETED"
    assert all(not agent.startswith("backend_") for agent in calls)
    assert "frontend_execution" in calls
    assert "deployment" in calls


async def test_list_versions_and_releases(client):
    _, tokens = await create_authenticated_user(client, email="lc-ver@example.com", username="lcver")
    _, project, requirement = await _seed_context(client, tokens["access_token"], "ver")
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await client.post(
        "/v1/change-requests",
        headers=auth_headers(tokens["access_token"]),
        json={
            "requirement_id": requirement["id"],
            "title": "Bug fix patch",
            "description": "api bug fix",
            "scope": "BACKEND_ONLY",
        },
    )
    run_id = created.json()["id"]
    with patch(
        "app.services.lifecycle.AgentDispatcher.dispatch_internal",
        new=AsyncMock(
            return_value=type(
                "DispatchResult",
                (),
                {"status": "completed", "output": {"id": "x", "live_url": "https://app.applyn.app"}, "log_messages": [], "error_message": None},
            )()
        ),
    ):
        executed = await client.post(
            "/v1/regeneration",
            headers=auth_headers(tokens["access_token"]),
            json={"regeneration_run_id": run_id},
        )
    assert executed.status_code == 200

    versions = await client.get(
        "/v1/application-versions",
        headers=auth_headers(tokens["access_token"]),
        params={"project_id": project["id"]},
    )
    assert versions.status_code == 200
    assert len(versions.json()) >= 1

    releases = await client.get(
        "/v1/releases",
        headers=auth_headers(tokens["access_token"]),
        params={"project_id": project["id"]},
    )
    assert releases.status_code == 200
    assert releases.json()["total"] >= 1
