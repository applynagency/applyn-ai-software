from unittest.mock import AsyncMock, patch

from app.schemas.backend_v1 import BackendDeveloperV1Output
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    mock_backend_v1_output,
    patch_backend_v1_agent,
    run_backend_v1,
    setup_backend_v1_pipeline,
    switch_organization,
)


async def test_developer_can_run_backend_v1(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="bv1-dev-owner@example.com", username="bv1devowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="bv1-dev-user@example.com", username="bv1devuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="BV1 Dev Org", slug="bv1-dev-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="bv1-dev-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="bv1-dev-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_backend_v1(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_developer_can_view_backend_v1_run(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="bv1-view-owner@example.com", username="bv1viewowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="bv1-view-dev@example.com", username="bv1viewdev"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="BV1 View Org", slug="bv1-view-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="bv1-view-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="bv1-view-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, owner_in_org["access_token"], requirement["id"])
    created = await run_backend_v1(client, owner_in_org["access_token"], requirement["id"])
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
        f"/v1/agents/backend-v1/runs/{created.json()['id']}",
        headers=auth_headers(dev_tokens["access_token"]),
    )
    assert response.status_code == 200


async def test_viewer_cannot_run_backend_v1(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="bv1-viewer-owner@example.com", username="bv1viewerowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="bv1-viewer@example.com", username="bv1viewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="BV1 Viewer Org", slug="bv1-viewer-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="bv1-vwr-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="bv1-vwr-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_backend_v1(client, viewer_tokens["access_token"], requirement["id"])
    assert response.status_code == 403


async def test_project_manager_can_run_backend_v1(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="bv1-pm-owner@example.com", username="bv1pmowner"
    )
    pm, _ = await create_authenticated_user(
        client, email="bv1-pm@example.com", username="bv1pm"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="BV1 PM Org", slug="bv1-pm-org"
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
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="bv1-pm-ws")
    project = await create_project(
        client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="bv1-pm-proj"
    )
    requirement = await create_requirement(
        client, pm_tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_backend_v1(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-fail-val@example.com", username="bv1failval"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_backend_v1_output()
    data = invalid.model_dump()
    data["api_specifications"] = data["api_specifications"][:1]
    invalid_output = BackendDeveloperV1Output(**data)
    with patch_backend_v1_agent():
        with patch(
            "app.services.backend_v1.BackendDeveloperV1Agent.run",
            new=AsyncMock(return_value=(invalid_output, 50)),
        ):
            response = await client.post(
                "/v1/agents/backend-v1/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
