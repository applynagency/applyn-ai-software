from unittest.mock import AsyncMock, patch

from app.schemas.frontend_execution import FrontendExecutionOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    patch_frontend_execution_agent,
    run_frontend_execution,
    setup_frontend_execution_pipeline,
    switch_organization,
)


async def test_developer_can_run_frontend_execution(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fe-dev-owner@example.com", username="fedevowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="fe-dev-user@example.com", username="fedevuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FE Dev Org", slug="fe-dev-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="fe-dev-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="fe-dev-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_execution_pipeline(
        client, owner_in_org["access_token"], requirement["id"]
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
    response = await run_frontend_execution(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_developer_can_view_frontend_execution_run(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fe-view-owner@example.com", username="feviewowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="fe-view-dev@example.com", username="feviewdev"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FE View Org", slug="fe-view-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="fe-view-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="fe-view-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_execution_pipeline(
        client, owner_in_org["access_token"], requirement["id"]
    )
    created = await run_frontend_execution(
        client, owner_in_org["access_token"], requirement["id"]
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
        f"/v1/agents/frontend-execution/runs/{created.json()['id']}",
        headers=auth_headers(dev_tokens["access_token"]),
    )
    assert response.status_code == 200


async def test_viewer_cannot_run_frontend_execution(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fe-viewer-owner@example.com", username="feviewerowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="fe-viewer@example.com", username="feviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FE Viewer Org", slug="fe-viewer-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="fe-vwr-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="fe-vwr-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_frontend_execution_pipeline(
        client, owner_in_org["access_token"], requirement["id"]
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_frontend_execution(
        client, viewer_tokens["access_token"], requirement["id"]
    )
    assert response.status_code == 403


async def test_project_manager_can_run_frontend_execution(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="fe-pm-owner@example.com", username="fepmowner"
    )
    pm, _ = await create_authenticated_user(
        client, email="fe-pm@example.com", username="fepm"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="FE PM Org", slug="fe-pm-org"
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
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="fe-pm-ws")
    project = await create_project(
        client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="fe-pm-proj"
    )
    requirement = await create_requirement(
        client, pm_tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_execution_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_frontend_execution(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-fail-val@example.com", username="fefailval"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    invalid_output = FrontendExecutionOutput(
        build_status="success",
        validation_status="passed",
        execution_logs=[],
        approval_status="FRONTEND_APPROVED",
        build_results={"status": "success"},
    )
    with patch_frontend_execution_agent():
        with patch(
            "app.services.frontend_execution.FrontendExecutionAgent.run",
            new=AsyncMock(return_value=invalid_output),
        ):
            response = await client.post(
                "/v1/agents/frontend-execution/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
