from unittest.mock import AsyncMock, patch

from app.schemas.observability_agent import ObservabilityAgentOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    mock_observability_agent_output,
    patch_observability_agent,
    run_observability_agents,
    setup_observability_pipeline,
    switch_organization,
)


async def test_developer_can_run_observability_agent(client):
    owner, owner_tokens = await create_authenticated_user(client, email="obs-dev-owner@example.com", username="obsdvowner")
    developer, _ = await create_authenticated_user(client, email="obs-dev@example.com", username="obsdvdev")
    organization = await create_organization(client, owner_tokens["access_token"], name="Obs Dev Org", slug="obs-dev-org")
    owner_in_org = await switch_organization(client, owner_tokens["access_token"], organization["id"])
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="obs-dev-ws")
    project = await create_project(client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="obs-dev-proj")
    requirement = await create_requirement(client, owner_in_org["access_token"], project_id=project["id"])
    await setup_observability_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(client, (await login_user(client, email=developer["email"]))["access_token"], organization["id"])
    response = await run_observability_agents(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_viewer_cannot_run_observability_agent(client):
    owner, owner_tokens = await create_authenticated_user(client, email="obs-viewer-owner@example.com", username="obsvwowner")
    viewer, _ = await create_authenticated_user(client, email="obs-viewer@example.com", username="obsvwview")
    organization = await create_organization(client, owner_tokens["access_token"], name="Obs View Org", slug="obs-view-org")
    owner_in_org = await switch_organization(client, owner_tokens["access_token"], organization["id"])
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="obs-view-ws")
    project = await create_project(client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="obs-view-proj")
    requirement = await create_requirement(client, owner_in_org["access_token"], project_id=project["id"])
    await setup_observability_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(client, (await login_user(client, email=viewer["email"]))["access_token"], organization["id"])
    response = await run_observability_agents(client, viewer_tokens["access_token"], requirement["id"])
    assert response.status_code == 403


async def test_project_manager_can_run_observability_agent(client):
    owner, owner_tokens = await create_authenticated_user(client, email="obs-pm-owner@example.com", username="obspmowner")
    pm, _ = await create_authenticated_user(client, email="obs-pm@example.com", username="obspmuser")
    organization = await create_organization(client, owner_tokens["access_token"], name="Obs PM Org", slug="obs-pm-org")
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": pm["id"], "role": "PROJECT_MANAGER"},
    )
    pm_tokens = await switch_organization(client, (await login_user(client, email=pm["email"]))["access_token"], organization["id"])
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="obs-pm-ws")
    project = await create_project(client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="obs-pm-proj")
    requirement = await create_requirement(client, pm_tokens["access_token"], project_id=project["id"])
    await setup_observability_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_observability_agents(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_unauthenticated_cannot_run_observability_agent(client):
    response = await client.post("/v1/agents/observability/run", json={"requirement_id": "missing"})
    assert response.status_code in (401, 403)


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(client, email="obs-val-fail@example.com", username="obsvalfail")
    workspace = await create_workspace(client, tokens["access_token"], slug="obs-fail-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="obs-fail-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_observability_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_observability_agent_output()
    data = invalid.model_dump(mode="json")
    data["alert_rules"] = []
    invalid_output = ObservabilityAgentOutput(**data)
    with patch_observability_agent():
        with patch("app.services.observability.ObservabilityAgent.run", new=AsyncMock(return_value=(invalid_output, 40))):
            response = await client.post(
                "/v1/agents/observability/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
