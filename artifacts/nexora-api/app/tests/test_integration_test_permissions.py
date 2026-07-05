from unittest.mock import AsyncMock, patch

from app.schemas.integration_test import IntegrationTestOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    mock_integration_test_output,
    patch_integration_test_agent,
    run_integration_tests,
    setup_integration_test_pipeline,
    switch_organization,
)


async def test_developer_can_run_integration_test(client):
    owner, owner_tokens = await create_authenticated_user(client, email="integration_test-dev-owner@example.com", username="integratdvo")
    developer, _ = await create_authenticated_user(client, email="integration_test-dev@example.com", username="integratdev")
    organization = await create_organization(client, owner_tokens["access_token"], name="IntegrationTest Dev Org", slug="integration_test-dev-org")
    owner_in_org = await switch_organization(client, owner_tokens["access_token"], organization["id"])
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="integration_test-dev-ws")
    project = await create_project(client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="integration_test-dev-proj")
    requirement = await create_requirement(client, owner_in_org["access_token"], project_id=project["id"])
    await setup_integration_test_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(client, (await login_user(client, email=developer["email"]))["access_token"], organization["id"])
    response = await run_integration_tests(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_viewer_cannot_run_integration_test(client):
    owner, owner_tokens = await create_authenticated_user(client, email="integration_test-viewer-owner@example.com", username="integratvow")
    viewer, _ = await create_authenticated_user(client, email="integration_test-viewer@example.com", username="integratviw")
    organization = await create_organization(client, owner_tokens["access_token"], name="IntegrationTest View Org", slug="integration_test-view-org")
    owner_in_org = await switch_organization(client, owner_tokens["access_token"], organization["id"])
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="integration_test-view-ws")
    project = await create_project(client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="integration_test-view-proj")
    requirement = await create_requirement(client, owner_in_org["access_token"], project_id=project["id"])
    await setup_integration_test_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(client, (await login_user(client, email=viewer["email"]))["access_token"], organization["id"])
    response = await run_integration_tests(client, viewer_tokens["access_token"], requirement["id"])
    assert response.status_code == 403


async def test_project_manager_can_run_integration_test(client):
    owner, owner_tokens = await create_authenticated_user(client, email="integration_test-pm-owner@example.com", username="integratpmo")
    pm, _ = await create_authenticated_user(client, email="integration_test-pm@example.com", username="integratpmx")
    organization = await create_organization(client, owner_tokens["access_token"], name="IntegrationTest PM Org", slug="integration_test-pm-org")
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": pm["id"], "role": "PROJECT_MANAGER"},
    )
    pm_tokens = await switch_organization(client, (await login_user(client, email=pm["email"]))["access_token"], organization["id"])
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="integration_test-pm-ws")
    project = await create_project(client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="integration_test-pm-proj")
    requirement = await create_requirement(client, pm_tokens["access_token"], project_id=project["id"])
    await setup_integration_test_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_integration_tests(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(client, email="integration_test-val-fail@example.com", username="integratfail")
    workspace = await create_workspace(client, tokens["access_token"], slug="integration_test-fail-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="integration_test-fail-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_integration_test_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_integration_test_output()
    data = invalid.model_dump(mode="json")
    data["api_test_cases"] = data["api_test_cases"][:1]
    invalid_output = IntegrationTestOutput(**data)
    with patch_integration_test_agent():
        with patch("app.services.integration_test.IntegrationTestAgent.run", new=AsyncMock(return_value=(invalid_output, 40))):
            response = await client.post(
                "/v1/agents/integration-tests/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
