from unittest.mock import AsyncMock, patch

from app.schemas.sre_approval import SreApprovalOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    mock_sre_approval_output,
    patch_sre_approval_agent,
    run_sre_approvals,
    setup_sre_approval_pipeline,
    switch_organization,
)


async def test_developer_can_run_sre_approval(client):
    owner, owner_tokens = await create_authenticated_user(client, email="sre-dev-owner@example.com", username="sredvowner")
    developer, _ = await create_authenticated_user(client, email="sre-dev@example.com", username="sredvdev")
    organization = await create_organization(client, owner_tokens["access_token"], name="Sre Dev Org", slug="sre-dev-org")
    owner_in_org = await switch_organization(client, owner_tokens["access_token"], organization["id"])
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="sre-dev-ws")
    project = await create_project(client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="sre-dev-proj")
    requirement = await create_requirement(client, owner_in_org["access_token"], project_id=project["id"])
    await setup_sre_approval_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(client, (await login_user(client, email=developer["email"]))["access_token"], organization["id"])
    response = await run_sre_approvals(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_viewer_cannot_run_sre_approval(client):
    owner, owner_tokens = await create_authenticated_user(client, email="sre-viewer-owner@example.com", username="srevwowner")
    viewer, _ = await create_authenticated_user(client, email="sre-viewer@example.com", username="srevwview")
    organization = await create_organization(client, owner_tokens["access_token"], name="Sre View Org", slug="sre-view-org")
    owner_in_org = await switch_organization(client, owner_tokens["access_token"], organization["id"])
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="sre-view-ws")
    project = await create_project(client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="sre-view-proj")
    requirement = await create_requirement(client, owner_in_org["access_token"], project_id=project["id"])
    await setup_sre_approval_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(client, (await login_user(client, email=viewer["email"]))["access_token"], organization["id"])
    response = await run_sre_approvals(client, viewer_tokens["access_token"], requirement["id"])
    assert response.status_code == 403


async def test_project_manager_can_run_sre_approval(client):
    owner, owner_tokens = await create_authenticated_user(client, email="sre-pm-owner@example.com", username="srepmowner")
    pm, _ = await create_authenticated_user(client, email="sre-pm@example.com", username="srepmuser")
    organization = await create_organization(client, owner_tokens["access_token"], name="Sre PM Org", slug="sre-pm-org")
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": pm["id"], "role": "PROJECT_MANAGER"},
    )
    pm_tokens = await switch_organization(client, (await login_user(client, email=pm["email"]))["access_token"], organization["id"])
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="sre-pm-ws")
    project = await create_project(client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="sre-pm-proj")
    requirement = await create_requirement(client, pm_tokens["access_token"], project_id=project["id"])
    await setup_sre_approval_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_sre_approvals(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_unauthenticated_cannot_run_sre_approval(client):
    response = await client.post("/v1/agents/sre-approval/run", json={"requirement_id": "missing"})
    assert response.status_code in (401, 403)


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(client, email="sre-val-fail@example.com", username="srevalfail")
    workspace = await create_workspace(client, tokens["access_token"], slug="sre-fail-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="sre-fail-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_sre_approval_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_sre_approval_output()
    data = invalid.model_dump(mode="json")
    data["findings"] = []
    data["recommendation"] = ""
    invalid_output = SreApprovalOutput(**data)
    with patch_sre_approval_agent():
        with patch("app.services.sre_approval.SreApprovalAgent.run", new=AsyncMock(return_value=(invalid_output, 40))):
            response = await client.post(
                "/v1/agents/sre-approval/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
