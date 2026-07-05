from unittest.mock import AsyncMock, patch

from app.schemas.frontend_architect import FrontendArchitectOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    mock_frontend_architect_output,
    patch_frontend_architect_agent,
    run_frontend_architect,
    setup_frontend_architect_pipeline,
    switch_organization,
)


async def test_developer_can_run_frontend_architect(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fa-dev-owner@example.com", username="fadevowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="fa-dev-user@example.com", username="fadevuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FA Dev Org", slug="fa-dev-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="fa-dev-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="fa-dev-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_frontend_architect(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_developer_can_view_frontend_architect_run(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fa-view-owner@example.com", username="faviewowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="fa-view-dev@example.com", username="faviewdev"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FA View Org", slug="fa-view-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="fa-view-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="fa-view-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, owner_in_org["access_token"], requirement["id"])
    created = await run_frontend_architect(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await client.get(
        f"/v1/agents/frontend-architect/runs/{created.json()['id']}",
        headers=auth_headers(dev_tokens["access_token"]),
    )
    assert response.status_code == 200


async def test_viewer_cannot_run_frontend_architect(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fa-viewer-owner@example.com", username="faviewerowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="fa-viewer@example.com", username="faviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FA Viewer Org", slug="fa-viewer-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="fa-vwr-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="fa-vwr-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_frontend_architect(client, viewer_tokens["access_token"], requirement["id"])
    assert response.status_code == 403


async def test_project_manager_can_run_frontend_architect(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fa-pm-owner@example.com", username="fapmowner"
    )
    pm, _ = await create_authenticated_user(
        client, email="fa-pm@example.com", username="fapm"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FA PM Org", slug="fa-pm-org"
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": pm["id"], "role": "PROJECT_MANAGER"},
    )
    pm_tokens = await switch_organization(
        client, (await login_user(client, email=pm["email"]))["access_token"],
        organization["id"],
    )
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="fa-pm-ws")
    project = await create_project(
        client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="fa-pm-proj"
    )
    requirement = await create_requirement(
        client, pm_tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_frontend_architect(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-fail-val@example.com", username="fafailval"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_frontend_architect_output()
    data = invalid.model_dump()
    data["page_architecture"] = data["page_architecture"][:1]
    invalid_output = FrontendArchitectOutput(**data)
    with patch_frontend_architect_agent():
        with patch(
            "app.services.frontend_architect.FrontendArchitectAgent.run",
            new=AsyncMock(return_value=(invalid_output, 50)),
        ):
            response = await client.post(
                "/v1/agents/frontend-architect/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
