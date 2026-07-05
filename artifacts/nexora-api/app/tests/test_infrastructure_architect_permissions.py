from unittest.mock import AsyncMock, patch

from app.schemas.infrastructure_architect import InfrastructureArchitectOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    mock_infrastructure_architect_output,
    patch_infrastructure_architect_agent,
    run_infrastructure_architects,
    setup_infrastructure_architect_pipeline,
    switch_organization,
)


async def test_developer_can_run_infrastructure_architect(client):
    owner, owner_tokens = await create_authenticated_user(client, email="infrastructure_architect-dev-owner@example.com", username="integratdvo")
    developer, _ = await create_authenticated_user(client, email="infrastructure_architect-dev@example.com", username="integratdev")
    organization = await create_organization(client, owner_tokens["access_token"], name="InfrastructureArchitect Dev Org", slug="infrastructure_architect-dev-org")
    owner_in_org = await switch_organization(client, owner_tokens["access_token"], organization["id"])
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="infrastructure_architect-dev-ws")
    project = await create_project(client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="infrastructure_architect-dev-proj")
    requirement = await create_requirement(client, owner_in_org["access_token"], project_id=project["id"])
    await setup_infrastructure_architect_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(client, (await login_user(client, email=developer["email"]))["access_token"], organization["id"])
    response = await run_infrastructure_architects(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_viewer_cannot_run_infrastructure_architect(client):
    owner, owner_tokens = await create_authenticated_user(client, email="infrastructure_architect-viewer-owner@example.com", username="integratvow")
    viewer, _ = await create_authenticated_user(client, email="infrastructure_architect-viewer@example.com", username="integratviw")
    organization = await create_organization(client, owner_tokens["access_token"], name="InfrastructureArchitect View Org", slug="infrastructure_architect-view-org")
    owner_in_org = await switch_organization(client, owner_tokens["access_token"], organization["id"])
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="infrastructure_architect-view-ws")
    project = await create_project(client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="infrastructure_architect-view-proj")
    requirement = await create_requirement(client, owner_in_org["access_token"], project_id=project["id"])
    await setup_infrastructure_architect_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(client, (await login_user(client, email=viewer["email"]))["access_token"], organization["id"])
    response = await run_infrastructure_architects(client, viewer_tokens["access_token"], requirement["id"])
    assert response.status_code == 403


async def test_project_manager_can_run_infrastructure_architect(client):
    owner, owner_tokens = await create_authenticated_user(client, email="infrastructure_architect-pm-owner@example.com", username="integratpmo")
    pm, _ = await create_authenticated_user(client, email="infrastructure_architect-pm@example.com", username="integratpmx")
    organization = await create_organization(client, owner_tokens["access_token"], name="InfrastructureArchitect PM Org", slug="infrastructure_architect-pm-org")
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": pm["id"], "role": "PROJECT_MANAGER"},
    )
    pm_tokens = await switch_organization(client, (await login_user(client, email=pm["email"]))["access_token"], organization["id"])
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="infrastructure_architect-pm-ws")
    project = await create_project(client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="infrastructure_architect-pm-proj")
    requirement = await create_requirement(client, pm_tokens["access_token"], project_id=project["id"])
    await setup_infrastructure_architect_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_infrastructure_architects(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(client, email="infrastructure_architect-val-fail@example.com", username="integratfail")
    workspace = await create_workspace(client, tokens["access_token"], slug="infrastructure_architect-fail-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="infrastructure_architect-fail-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_infrastructure_architect_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_infrastructure_architect_output()
    data = invalid.model_dump(mode="json")
    data["environments"] = data["environments"][:1]
    invalid_output = InfrastructureArchitectOutput(**data)
    with patch_infrastructure_architect_agent():
        with patch("app.services.infrastructure_architect.InfrastructureArchitectAgent.run", new=AsyncMock(return_value=(invalid_output, 40))):
            response = await client.post(
                "/v1/agents/infrastructure-architect/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
