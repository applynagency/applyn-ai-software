from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_integration_tests,
    setup_integration_test_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(client, email="integration_test-schema@example.com", username="integratsch")
    workspace = await create_workspace(client, tokens["access_token"], slug="integration_test-schema-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="integration_test-schema-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_integration_test_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_integration_tests(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    assert "api_test_cases" in artifact
    assert "frontend_backend_flows" in artifact
    assert "database_validation" in artifact
    assert "integration_coverage" in artifact



async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(client, email="integration_test-meta@example.com", username="integratmet")
    workspace = await create_workspace(client, tokens["access_token"], slug="integration_test-meta-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="integration_test-meta-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_integration_test_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_integration_tests(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None
    assert data["artifact"]["model_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(client, email="integration_test-history@example.com", username="integrathst")
    workspace = await create_workspace(client, tokens["access_token"], slug="integration_test-hist-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="integration_test-hist-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_integration_test_pipeline(client, tokens["access_token"], requirement["id"])
    await run_integration_tests(client, tokens["access_token"], requirement["id"])
    await run_integration_tests(client, tokens["access_token"], requirement["id"])
    response = await client.get(f"/v1/agents/integration-tests/{requirement['id']}", headers=auth_headers(tokens["access_token"]))
    assert response.json()["total"] >= 2


async def test_required_counts_meet_minimums(client):
    _, tokens = await create_authenticated_user(client, email="integration_test-mins@example.com", username="integratmin")
    workspace = await create_workspace(client, tokens["access_token"], slug="integration_test-min-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="integration_test-min-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_integration_test_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_integration_tests(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    assert len(artifact["api_test_cases"]) >= 8
    assert len(artifact["frontend_backend_flows"]) >= 5
    assert len(artifact["database_validation"]) >= 5
