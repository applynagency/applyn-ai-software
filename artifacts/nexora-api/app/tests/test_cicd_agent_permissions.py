from unittest.mock import AsyncMock, patch

from app.schemas.cicd_agent import CicdAgentOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    mock_cicd_agent_output,
    patch_cicd_agent,
    run_cicd_agents,
    setup_cicd_agent_pipeline,
    switch_organization,
)


async def test_developer_can_run_cicd_agent(client):
    owner, owner_tokens = await create_authenticated_user(client, email="cicd_agent-dev-owner@example.com", username="integratdvo")
    developer, _ = await create_authenticated_user(client, email="cicd_agent-dev@example.com", username="integratdev")
    organization = await create_organization(client, owner_tokens["access_token"], name="CicdAgent Dev Org", slug="cicd_agent-dev-org")
    owner_in_org = await switch_organization(client, owner_tokens["access_token"], organization["id"])
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="cicd_agent-dev-ws")
    project = await create_project(client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="cicd_agent-dev-proj")
    requirement = await create_requirement(client, owner_in_org["access_token"], project_id=project["id"])
    await setup_cicd_agent_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(client, (await login_user(client, email=developer["email"]))["access_token"], organization["id"])
    response = await run_cicd_agents(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_viewer_cannot_run_cicd_agent(client):
    owner, owner_tokens = await create_authenticated_user(client, email="cicd_agent-viewer-owner@example.com", username="integratvow")
    viewer, _ = await create_authenticated_user(client, email="cicd_agent-viewer@example.com", username="integratviw")
    organization = await create_organization(client, owner_tokens["access_token"], name="CicdAgent View Org", slug="cicd_agent-view-org")
    owner_in_org = await switch_organization(client, owner_tokens["access_token"], organization["id"])
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="cicd_agent-view-ws")
    project = await create_project(client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="cicd_agent-view-proj")
    requirement = await create_requirement(client, owner_in_org["access_token"], project_id=project["id"])
    await setup_cicd_agent_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(client, (await login_user(client, email=viewer["email"]))["access_token"], organization["id"])
    response = await run_cicd_agents(client, viewer_tokens["access_token"], requirement["id"])
    assert response.status_code == 403


async def test_project_manager_can_run_cicd_agent(client):
    owner, owner_tokens = await create_authenticated_user(client, email="cicd_agent-pm-owner@example.com", username="integratpmo")
    pm, _ = await create_authenticated_user(client, email="cicd_agent-pm@example.com", username="integratpmx")
    organization = await create_organization(client, owner_tokens["access_token"], name="CicdAgent PM Org", slug="cicd_agent-pm-org")
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": pm["id"], "role": "PROJECT_MANAGER"},
    )
    pm_tokens = await switch_organization(client, (await login_user(client, email=pm["email"]))["access_token"], organization["id"])
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="cicd_agent-pm-ws")
    project = await create_project(client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="cicd_agent-pm-proj")
    requirement = await create_requirement(client, pm_tokens["access_token"], project_id=project["id"])
    await setup_cicd_agent_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_cicd_agents(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(client, email="cicd_agent-val-fail@example.com", username="integratfail")
    workspace = await create_workspace(client, tokens["access_token"], slug="cicd_agent-fail-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="cicd_agent-fail-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_cicd_agent_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_cicd_agent_output()
    data = invalid.model_dump(mode="json")
    data["github_actions"] = ""
    invalid_output = CicdAgentOutput(**data)
    with patch_cicd_agent():
        with patch("app.services.cicd.CicdAgent.run", new=AsyncMock(return_value=(invalid_output, 40))):
            response = await client.post(
                "/v1/agents/cicd/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
