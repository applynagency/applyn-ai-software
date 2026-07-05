from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_integration_tests,
    setup_integration_test_pipeline,
)


async def test_run_integration_test_success(client):
    _, tokens = await create_authenticated_user(client, email="integration_test-run@example.com", username="integratrun")
    workspace = await create_workspace(client, tokens["access_token"], slug="integration_test-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="integration_test-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_integration_test_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_integration_tests(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_prerequisites(client):
    _, tokens = await create_authenticated_user(client, email="integration_test-no-pre@example.com", username="integratnop")
    workspace = await create_workspace(client, tokens["access_token"], slug="integration_test-no-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="integration_test-no-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    response = await run_integration_tests(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_integration_test_run(client):
    _, tokens = await create_authenticated_user(client, email="integration_test-get@example.com", username="integratget")
    workspace = await create_workspace(client, tokens["access_token"], slug="integration_test-get-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="integration_test-get-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_integration_test_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_integration_tests(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(f"/v1/agents/integration-tests/runs/{run_id}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_integration_test_artifact(client):
    _, tokens = await create_authenticated_user(client, email="integration_test-artifact@example.com", username="integratart")
    workspace = await create_workspace(client, tokens["access_token"], slug="integration_test-art-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="integration_test-art-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_integration_test_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_integration_tests(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(f"/v1/agents/integration-tests/artifacts/{artifact_id}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["artifact_json"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(client, email="integration_test-list@example.com", username="integratlst")
    workspace = await create_workspace(client, tokens["access_token"], slug="integration_test-list-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="integration_test-list-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_integration_test_pipeline(client, tokens["access_token"], requirement["id"])
    await run_integration_tests(client, tokens["access_token"], requirement["id"])
    response = await client.get(f"/v1/agents/integration-tests/{requirement['id']}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["total"] >= 1
