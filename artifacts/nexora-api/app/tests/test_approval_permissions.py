from unittest.mock import AsyncMock, patch

from app.schemas.approval import ApprovalWorkflowOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    patch_approval_workflow_agent,
    run_approval,
    setup_approval_pipeline,
    switch_organization,
)


async def test_developer_can_run_approval(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="appr-dev-owner@example.com", username="apprdevowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="appr-dev-user@example.com", username="apprdevuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Appr Dev Org", slug="appr-dev-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="appr-dev-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="appr-dev-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_approval(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_developer_can_view_approval_run(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="appr-view-owner@example.com", username="apprviewowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="appr-view-dev@example.com", username="apprviewdev"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Appr View Org", slug="appr-view-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="appr-view-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="appr-view-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, owner_in_org["access_token"], requirement["id"])
    created = await run_approval(client, owner_in_org["access_token"], requirement["id"])
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
        f"/v1/agents/approval/runs/{created.json()['id']}",
        headers=auth_headers(dev_tokens["access_token"]),
    )
    assert response.status_code == 200


async def test_viewer_cannot_run_approval(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="appr-viewer-owner@example.com", username="apprviewerowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="appr-viewer@example.com", username="apprviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Appr Viewer Org", slug="appr-viewer-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="appr-vwr-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="appr-vwr-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"],
        organization["id"],
    )
    response = await run_approval(client, viewer_tokens["access_token"], requirement["id"])
    assert response.status_code == 403


async def test_project_manager_can_run_approval(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="appr-pm-owner@example.com", username="apprpmowner"
    )
    pm, _ = await create_authenticated_user(
        client, email="appr-pm@example.com", username="apprpm"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="Appr PM Org", slug="appr-pm-org"
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
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="appr-pm-ws")
    project = await create_project(
        client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="appr-pm-proj"
    )
    requirement = await create_requirement(
        client, pm_tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_approval(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_validation_failure_returns_422_without_persisted_run(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-fail-val@example.com", username="apprfailval"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    invalid_output = ApprovalWorkflowOutput.model_construct(
        approval_summary={},
        review_checklist=[],
        deployment_readiness={},
        recommendation="APPROVE",
        approval_status="UNDER_REVIEW",
    )
    with patch_approval_workflow_agent():
        with patch(
            "app.services.approval.ApprovalWorkflowAgent.run",
            new=AsyncMock(return_value=invalid_output),
        ):
            response = await client.post(
                "/v1/agents/approval/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
    list_response = await client.get(
        f"/v1/agents/approval/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert list_response.json()["total"] == 0
