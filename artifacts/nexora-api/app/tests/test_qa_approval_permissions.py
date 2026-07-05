from unittest.mock import AsyncMock, patch

from app.schemas.qa_approval import QAApprovalOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    mock_qa_approval_output,
    patch_qa_approval_agent,
    run_qa_approval,
    setup_qa_approval_pipeline,
    switch_organization,
)


async def test_developer_can_run_qa_approval(client):
    owner, owner_tokens = await create_authenticated_user(client, email="qa_approval-dev-owner@example.com", username="qa_approdvo")
    developer, _ = await create_authenticated_user(client, email="qa_approval-dev@example.com", username="qa_approdev")
    organization = await create_organization(client, owner_tokens["access_token"], name="QaApproval Dev Org", slug="qa_approval-dev-org")
    owner_in_org = await switch_organization(client, owner_tokens["access_token"], organization["id"])
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="qa_approval-dev-ws")
    project = await create_project(client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="qa_approval-dev-proj")
    requirement = await create_requirement(client, owner_in_org["access_token"], project_id=project["id"])
    await setup_qa_approval_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(client, (await login_user(client, email=developer["email"]))["access_token"], organization["id"])
    response = await run_qa_approval(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_viewer_cannot_run_qa_approval(client):
    owner, owner_tokens = await create_authenticated_user(client, email="qa_approval-viewer-owner@example.com", username="qa_approvow")
    viewer, _ = await create_authenticated_user(client, email="qa_approval-viewer@example.com", username="qa_approviw")
    organization = await create_organization(client, owner_tokens["access_token"], name="QaApproval View Org", slug="qa_approval-view-org")
    owner_in_org = await switch_organization(client, owner_tokens["access_token"], organization["id"])
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="qa_approval-view-ws")
    project = await create_project(client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="qa_approval-view-proj")
    requirement = await create_requirement(client, owner_in_org["access_token"], project_id=project["id"])
    await setup_qa_approval_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(client, (await login_user(client, email=viewer["email"]))["access_token"], organization["id"])
    response = await run_qa_approval(client, viewer_tokens["access_token"], requirement["id"])
    assert response.status_code == 403


async def test_project_manager_can_run_qa_approval(client):
    owner, owner_tokens = await create_authenticated_user(client, email="qa_approval-pm-owner@example.com", username="qa_appropmo")
    pm, _ = await create_authenticated_user(client, email="qa_approval-pm@example.com", username="qa_appropmx")
    organization = await create_organization(client, owner_tokens["access_token"], name="QaApproval PM Org", slug="qa_approval-pm-org")
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": pm["id"], "role": "PROJECT_MANAGER"},
    )
    pm_tokens = await switch_organization(client, (await login_user(client, email=pm["email"]))["access_token"], organization["id"])
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="qa_approval-pm-ws")
    project = await create_project(client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="qa_approval-pm-proj")
    requirement = await create_requirement(client, pm_tokens["access_token"], project_id=project["id"])
    await setup_qa_approval_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_qa_approval(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(client, email="qa_approval-val-fail@example.com", username="qa_approfail")
    workspace = await create_workspace(client, tokens["access_token"], slug="qa_approval-fail-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="qa_approval-fail-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_qa_approval_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_qa_approval_output()
    data = invalid.model_dump(mode="json")
    data["findings"] = []
    invalid_output = QAApprovalOutput(**data)
    with patch_qa_approval_agent():
        with patch("app.services.qa_approval.QAApprovalAgent.run", new=AsyncMock(return_value=(invalid_output, 40))):
            response = await client.post(
                "/v1/agents/qa-approvals/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
