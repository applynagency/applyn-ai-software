from unittest.mock import AsyncMock, patch

from app.schemas.backend_architect import BackendArchitectOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    login_user,
    mock_backend_architect_output,
    patch_backend_architect_agent,
    run_backend_architect,
    setup_backend_architect_pipeline,
    switch_organization,
)


async def test_developer_can_run_backend_architect(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="ba-arch-dev-owner@example.com", username="baarchdevowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="ba-arch-dev-user@example.com", username="baarchdevuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="BA Arch Dev Org", slug="ba-arch-dev-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    ctx = await setup_backend_architect_pipeline(client, owner_in_org["access_token"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_backend_architect(
        client, dev_tokens["access_token"], ctx["requirement"]["id"]
    )
    assert response.status_code == 201


async def test_developer_can_view_backend_architect_run(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="ba-arch-view-owner@example.com", username="baarchviewowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="ba-arch-view-dev@example.com", username="baarchviewdev"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="BA Arch View Org", slug="ba-arch-view-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    ctx = await setup_backend_architect_pipeline(client, owner_in_org["access_token"])
    created = await run_backend_architect(
        client, owner_in_org["access_token"], ctx["requirement"]["id"]
    )
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
        f"/v1/agents/backend-architect/runs/{created.json()['id']}",
        headers=auth_headers(dev_tokens["access_token"]),
    )
    assert response.status_code == 200


async def test_viewer_cannot_run_backend_architect(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="ba-arch-viewer-owner@example.com", username="baarchviewerowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="ba-arch-viewer@example.com", username="baarchviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="BA Arch Viewer Org", slug="ba-arch-viewer-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    ctx = await setup_backend_architect_pipeline(client, owner_in_org["access_token"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_backend_architect(
        client, viewer_tokens["access_token"], ctx["requirement"]["id"]
    )
    assert response.status_code == 403


async def test_project_manager_can_run_backend_architect(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="ba-arch-pm-owner@example.com", username="baarchpmowner"
    )
    pm, _ = await create_authenticated_user(
        client, email="ba-arch-pm@example.com", username="baarchpm"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="BA Arch PM Org", slug="ba-arch-pm-org"
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
    ctx = await setup_backend_architect_pipeline(client, pm_tokens["access_token"])
    response = await run_backend_architect(
        client, pm_tokens["access_token"], ctx["requirement"]["id"]
    )
    assert response.status_code == 201


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-fail-val@example.com", username="baarchfailval"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    invalid = mock_backend_architect_output()
    data = invalid.model_dump()
    data["api_architecture"] = data["api_architecture"][:1]
    invalid_output = BackendArchitectOutput(**data)
    with patch_backend_architect_agent():
        with patch(
            "app.services.backend_architect.BackendArchitectAgent.run",
            new=AsyncMock(return_value=(invalid_output, 50)),
        ):
            response = await client.post(
                "/v1/agents/backend-architect/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": ctx["requirement"]["id"]},
            )
    assert response.status_code == 422
