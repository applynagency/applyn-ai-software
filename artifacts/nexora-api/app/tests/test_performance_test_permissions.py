from unittest.mock import AsyncMock, patch

from app.schemas.performance_test import PerformanceTestOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    mock_performance_test_output,
    patch_performance_test_agent,
    run_performance_tests,
    setup_performance_test_pipeline,
    switch_organization,
)


async def test_developer_can_run_performance_test(client):
    owner, owner_tokens = await create_authenticated_user(client, email="performance_test-dev-owner@example.com", username="performadvo")
    developer, _ = await create_authenticated_user(client, email="performance_test-dev@example.com", username="performadev")
    organization = await create_organization(client, owner_tokens["access_token"], name="PerformanceTest Dev Org", slug="performance_test-dev-org")
    owner_in_org = await switch_organization(client, owner_tokens["access_token"], organization["id"])
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="performance_test-dev-ws")
    project = await create_project(client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="performance_test-dev-proj")
    requirement = await create_requirement(client, owner_in_org["access_token"], project_id=project["id"])
    await setup_performance_test_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": developer["id"], "role": "DEVELOPER"},
    )
    dev_tokens = await switch_organization(client, (await login_user(client, email=developer["email"]))["access_token"], organization["id"])
    response = await run_performance_tests(client, dev_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_viewer_cannot_run_performance_test(client):
    owner, owner_tokens = await create_authenticated_user(client, email="performance_test-viewer-owner@example.com", username="performavow")
    viewer, _ = await create_authenticated_user(client, email="performance_test-viewer@example.com", username="performaviw")
    organization = await create_organization(client, owner_tokens["access_token"], name="PerformanceTest View Org", slug="performance_test-view-org")
    owner_in_org = await switch_organization(client, owner_tokens["access_token"], organization["id"])
    workspace = await create_workspace(client, owner_in_org["access_token"], slug="performance_test-view-ws")
    project = await create_project(client, owner_in_org["access_token"], workspace_id=workspace["id"], slug="performance_test-view-proj")
    requirement = await create_requirement(client, owner_in_org["access_token"], project_id=project["id"])
    await setup_performance_test_pipeline(client, owner_in_org["access_token"], requirement["id"])
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": viewer["id"], "role": "VIEWER"},
    )
    viewer_tokens = await switch_organization(client, (await login_user(client, email=viewer["email"]))["access_token"], organization["id"])
    response = await run_performance_tests(client, viewer_tokens["access_token"], requirement["id"])
    assert response.status_code == 403


async def test_project_manager_can_run_performance_test(client):
    owner, owner_tokens = await create_authenticated_user(client, email="performance_test-pm-owner@example.com", username="performapmo")
    pm, _ = await create_authenticated_user(client, email="performance_test-pm@example.com", username="performapmx")
    organization = await create_organization(client, owner_tokens["access_token"], name="PerformanceTest PM Org", slug="performance_test-pm-org")
    await client.post(
        f"/v1/organizations/{organization['id']}/members",
        headers=auth_headers(owner_tokens["access_token"]),
        json={"user_id": pm["id"], "role": "PROJECT_MANAGER"},
    )
    pm_tokens = await switch_organization(client, (await login_user(client, email=pm["email"]))["access_token"], organization["id"])
    workspace = await create_workspace(client, pm_tokens["access_token"], slug="performance_test-pm-ws")
    project = await create_project(client, pm_tokens["access_token"], workspace_id=workspace["id"], slug="performance_test-pm-proj")
    requirement = await create_requirement(client, pm_tokens["access_token"], project_id=project["id"])
    await setup_performance_test_pipeline(client, pm_tokens["access_token"], requirement["id"])
    response = await run_performance_tests(client, pm_tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_validation_failure_marks_run_failed(client):
    _, tokens = await create_authenticated_user(client, email="performance_test-val-fail@example.com", username="performafail")
    workspace = await create_workspace(client, tokens["access_token"], slug="performance_test-fail-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="performance_test-fail-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_performance_test_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_performance_test_output()
    data = invalid.model_dump(mode="json")
    data["load_test_plan"] = data["load_test_plan"][:1]
    invalid_output = PerformanceTestOutput(**data)
    with patch_performance_test_agent():
        with patch("app.services.performance_test.PerformanceTestAgent.run", new=AsyncMock(return_value=(invalid_output, 40))):
            response = await client.post(
                "/v1/agents/performance-tests/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
