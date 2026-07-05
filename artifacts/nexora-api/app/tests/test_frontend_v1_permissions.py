from unittest.mock import AsyncMock, patch

from app.schemas.frontend_v1 import FrontendDeveloperV1Output
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    mock_frontend_v1_output,
    patch_frontend_v1_agent,
    run_frontend_v1,
    setup_frontend_v1_pipeline,
    switch_organization,
)


async def test_developer_can_run_frontend_v1(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fv1-dev-owner@example.com", username="fv1devowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="fv1-dev-user@example.com", username="fv1devuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FV1 Dev Org", slug="fv1-dev-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="fv1-dev-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="fv1-dev-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_frontend_v1(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_developer_can_view_frontend_v1_run(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fv1-view-owner@example.com", username="fv1viewowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="fv1-view-dev@example.com", username="fv1viewdev"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FV1 View Org", slug="fv1-view-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="fv1-view-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="fv1-view-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, owner_in_org["access_token"], requirement["id"])
    created = await run_frontend_v1(client, owner_in_org["access_token"], requirement["id"])
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
        f"/v1/agents/frontend-v1/runs/{created.json()['id']}",
        headers=auth_headers(dev_tokens["access_token"]),
    )
    assert response.status_code == 200


async def test_viewer_cannot_run_frontend_v1(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fv1-viewer-owner@example.com", username="fv1viewerowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="fv1-viewer@example.com", username="fv1viewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FV1 Viewer Org", slug="fv1-viewer-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="fv1-vwr-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="fv1-vwr-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_frontend_v1(client, viewer_tokens["access_token"], requirement["id"])
    assert response.status_code == 403


async def test_project_manager_can_run_frontend_v1(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fv1-pm-owner@example.com", username="fv1pmowner"
    )
    pm, _ = await create_authenticated_user(
        client, email="fv1-pm@example.com", username="fv1pm"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FV1 PM Org", slug="fv1-pm-org"
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
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="fv1-pm-ws")
    project = await create_project(
        client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="fv1-pm-proj"
    )
    requirement = await create_requirement(
        client, pm_tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_frontend_v1(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-fail-val@example.com", username="fv1failval"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_frontend_v1_output()
    data = invalid.model_dump()
    data["page_structure"] = data["page_structure"][:1]
    invalid_output = FrontendDeveloperV1Output(**data)
    with patch_frontend_v1_agent():
        with patch(
            "app.services.frontend_v1.FrontendDeveloperV1Agent.run",
            new=AsyncMock(return_value=(invalid_output, 50)),
        ):
            response = await client.post(
                "/v1/agents/frontend-v1/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
