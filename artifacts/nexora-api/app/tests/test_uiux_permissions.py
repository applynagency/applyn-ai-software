from unittest.mock import AsyncMock, patch

from app.schemas.uiux_designer import UIUXDesignerOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    mock_uiux_designer_output,
    patch_uiux_designer_agent,
    run_uiux_designer,
    setup_uiux_pipeline,
    switch_organization,
)


async def test_developer_can_run_uiux_designer(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="uiux-dev-owner@example.com", username="uiuxdevowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="uiux-dev-user@example.com", username="uiuxdevuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="UIUX Dev Org", slug="uiux-dev-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="uiux-dev-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="uiux-dev-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_uiux_designer(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_developer_can_view_uiux_run(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="uiux-view-owner@example.com", username="uiuxviewowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="uiux-view-dev@example.com", username="uiuxviewdev"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="UIUX View Org", slug="uiux-view-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="uiux-view-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="uiux-view-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, owner_in_org["access_token"], requirement["id"])
    created = await run_uiux_designer(client, owner_in_org["access_token"], requirement["id"])
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
        f"/v1/agents/uiux/runs/{created.json()['id']}",
        headers=auth_headers(dev_tokens["access_token"]),
    )
    assert response.status_code == 200


async def test_viewer_cannot_run_uiux_designer(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="uiux-viewer-owner@example.com", username="uiuxviewerowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="uiux-viewer@example.com", username="uiuxviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="UIUX Viewer Org", slug="uiux-viewer-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="uiux-vwr-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="uiux-vwr-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_uiux_designer(client, viewer_tokens["access_token"], requirement["id"])
    assert response.status_code == 403


async def test_project_manager_can_run_uiux_designer(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="uiux-pm-owner@example.com", username="uiuxpmowner"
    )
    pm, _ = await create_authenticated_user(
        client, email="uiux-pm@example.com", username="uiuxpm"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="UIUX PM Org", slug="uiux-pm-org"
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
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="uiux-pm-ws")
    project = await create_project(
        client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="uiux-pm-proj"
    )
    requirement = await create_requirement(
        client, pm_tokens["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_uiux_designer(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-fail-val@example.com", username="uiuxfailval"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="uiux-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="uiux-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_uiux_designer_output()
    data = invalid.model_dump()
    data["screen_inventory"] = data["screen_inventory"][:1]
    invalid_output = UIUXDesignerOutput(**data)
    with patch_uiux_designer_agent():
        with patch(
            "app.services.uiux_designer.UIUXDesignerAgent.run",
            new=AsyncMock(return_value=(invalid_output, 50)),
        ):
            response = await client.post(
                "/v1/agents/uiux/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
