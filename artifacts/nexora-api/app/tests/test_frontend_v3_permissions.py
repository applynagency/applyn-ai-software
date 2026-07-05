from unittest.mock import AsyncMock, patch

from app.schemas.frontend_v3 import FrontendDeveloperV3Output
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    mock_frontend_v3_output,
    patch_frontend_v3_agent,
    run_frontend_v3,
    setup_frontend_v3_pipeline,
    switch_organization,
)


async def test_developer_can_run_frontend_v3(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fv3-dev-owner@example.com", username="fv3devowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="fv3-dev-user@example.com", username="fv3devuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FV3 Dev Org", slug="fv3-dev-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="fv3-dev-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="fv3-dev-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_v3_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_frontend_v3(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_developer_can_view_frontend_v3_run(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fv3-view-owner@example.com", username="fv3viewowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="fv3-view-dev@example.com", username="fv3viewdev"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FV3 View Org", slug="fv3-view-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="fv3-view-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="fv3-view-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_v3_pipeline(client, owner_in_org["access_token"], requirement["id"])
    created = await run_frontend_v3(client, owner_in_org["access_token"], requirement["id"])
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
        f"/v1/agents/frontend-v3/runs/{created.json()['id']}",
        headers=auth_headers(dev_tokens["access_token"]),
    )
    assert response.status_code == 200


async def test_viewer_cannot_run_frontend_v3(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fv3-viewer-owner@example.com", username="fv3viewerowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="fv3-viewer@example.com", username="fv3viewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FV3 Viewer Org", slug="fv3-viewer-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="fv3-vwr-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="fv3-vwr-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_v3_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_frontend_v3(client, viewer_tokens["access_token"], requirement["id"])
    assert response.status_code == 403


async def test_project_manager_can_run_frontend_v3(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fv3-pm-owner@example.com", username="fv3pmowner"
    )
    pm, _ = await create_authenticated_user(
        client, email="fv3-pm@example.com", username="fv3pm"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FV3 PM Org", slug="fv3-pm-org"
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
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="fv3-pm-ws")
    project = await create_project(
        client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="fv3-pm-proj"
    )
    requirement = await create_requirement(
        client, pm_tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v3_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_frontend_v3(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(
        client, email="fv3-fail-val@example.com", username="fv3failval"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv3-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv3-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v3_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_frontend_v3_output()
    data = invalid.model_dump()
    data["generated_files"] = data["generated_files"][:1]
    invalid_output = FrontendDeveloperV3Output(**data)
    with patch_frontend_v3_agent():
        with patch(
            "app.services.frontend_v3.FrontendDeveloperV3Agent.run",
            new=AsyncMock(return_value=(invalid_output, 50)),
        ):
            response = await client.post(
                "/v1/agents/frontend-v3/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
