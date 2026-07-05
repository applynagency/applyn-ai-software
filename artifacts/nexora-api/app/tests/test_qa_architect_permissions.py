from unittest.mock import AsyncMock, patch

from app.schemas.qa_architect import QAArchitectOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    mock_qa_architect_output,
    patch_qa_architect_agent,
    run_qa_architect,
    setup_qa_architect_pipeline,
    switch_organization,
)


async def test_developer_can_run_qa_architect(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="qa-dev-owner@example.com", username="qadevowner"
    )
    developer, _ = await create_authenticated_user(
        client, email="qa-dev-user@example.com", username="qadevuser"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="QA Dev Org", slug="qa-dev-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="qa-dev-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="qa-dev-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(
        client, (await login_user(client, email=developer["email"]))["access_token"], organization["id"]
    )
    response = await run_qa_architect(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_viewer_cannot_run_qa_architect(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="qa-view-owner@example.com", username="qaviewowner"
    )
    viewer, _ = await create_authenticated_user(
        client, email="qa-viewer@example.com", username="qaviewer"
    )
    organization = await create_organization(
        client, owner_tokens["access_token"], name="QA Viewer Org", slug="qa-view-org"
    )
    owner_in_org = await switch_organization(
        client, owner_tokens["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="qa-view-ws")
    project = await create_project(
        client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="qa-view-proj"
    )
    requirement = await create_requirement(
        client, owner_in_org["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(
        client, (await login_user(client, email=viewer["email"]))["access_token"], organization["id"]
    )
    response = await run_qa_architect(client, viewer_tokens["access_token"], requirement["id"])
    assert response.status_code == 403


async def test_project_manager_can_run_qa_architect(client):
    owner, owner_tokens = await create_authenticated_user(
        client, email="qa-pm-owner@example.com", username="qapmowner"
    )
    pm, _ = await create_authenticated_user(client, email="qa-pm@example.com", username="qapm")
    organization = await create_organization(
        client, owner_tokens["access_token"], name="QA PM Org", slug="qa-pm-org"
    )
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": pm["id"], "role": "PROJECT_MANAGER"},
    )
    pm_tokens = await switch_organization(
        client, (await login_user(client, email=pm["email"]))["access_token"], organization["id"]
    )
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="qa-pm-ws")
    project = await create_project(
        client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="qa-pm-proj"
    )
    requirement = await create_requirement(
        client, pm_tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_qa_architect(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(
        client, email="qa-fail-val@example.com", username="qafailval"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="qa-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="qa-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_qa_architect_output()
    data = invalid.model_dump()
    data["test_coverage_matrix"] = data["test_coverage_matrix"][:2]
    invalid_output = QAArchitectOutput(**data)
    with patch_qa_architect_agent():
        with patch(
            "app.services.qa_architect.QAArchitectAgent.run",
            new=AsyncMock(return_value=(invalid_output, 50)),
        ):
            response = await client.post(
                "/v1/agents/qa-architect/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
