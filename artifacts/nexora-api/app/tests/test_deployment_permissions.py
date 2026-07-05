from unittest.mock import AsyncMock, patch

from app.schemas.deployment import DeploymentOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    patch_deployment_agent,
    run_deployment,
    setup_deployment_pipeline,
    switch_organization,
)


async def test_developer_can_run_deployment(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="dep-dev-owner@example.com", username="depdevowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="dep-dev-user@example.com", username="depdevuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Dep Dev Org", slug="dep-dev-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="dep-dev-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="dep-dev-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_deployment(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_developer_can_view_deployment_run(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="dep-view-owner@example.com", username="depviewowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="dep-view-dev@example.com", username="depviewdev"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Dep View Org", slug="dep-view-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="dep-view-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="dep-view-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, owner_in_org["access_token"], requirement["id"])
    created = await run_deployment(client, owner_in_org["access_token"], requirement["id"])
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
        f"/v1/agents/deployment/runs/{created.json()['id']}",
        headers=auth_headers(dev_tokens["access_token"]),
    )
    assert response.status_code == 200


async def test_viewer_cannot_run_deployment(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="dep-viewer-owner@example.com", username="depviewerowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="dep-viewer@example.com", username="depviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Dep Viewer Org", slug="dep-viewer-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="dep-vwr-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="dep-vwr-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_deployment(client, viewer_tokens["access_token"], requirement["id"])
    assert response.status_code == 403


async def test_project_manager_can_run_deployment(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="dep-pm-owner@example.com", username="deppmowner"
    )
    pm, _ = await create_authenticated_user(
        client, email="dep-pm@example.com", username="deppm"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Dep PM Org", slug="dep-pm-org"
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
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="dep-pm-ws")
    project = await create_project(
        client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="dep-pm-proj"
    )
    requirement = await create_requirement(
        client, pm_tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_deployment(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_validation_failure_returns_422_without_persisted_run(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-fail-val@example.com", username="depfailval"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    invalid_output = DeploymentOutput.model_construct(
        deployment_provider="AZURE",
        deployment_status="DEPLOYED",
        live_url="",
        deployment_logs=[],
    )
    with patch_deployment_agent():
        with patch(
            "app.services.deployment.DeploymentAgent.run",
            new=AsyncMock(return_value=invalid_output),
        ):
            response = await client.post(
                "/v1/agents/deployment/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
    list_response = await client.get(
        f"/v1/agents/deployment/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert list_response.json()["total"] == 0


async def test_viewer_cannot_rollback_deployment(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="dep-rb-viewer-owner@example.com", username="deprbviewerowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="dep-rb-viewer@example.com", username="deprbviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Dep RB Viewer Org", slug="dep-rb-viewer-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="dep-rb-vwr-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="dep-rb-vwr-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, owner_in_org["access_token"], requirement["id"])
    created = await run_deployment(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"],
        organization["id"],
    )
    response = await client.post(
        f"/v1/deployments/{created.json()['id']}/rollback",
        headers=auth_headers(viewer_tokens["access_token"]),
    )
    assert response.status_code == 403
