from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_performance_tests,
    setup_performance_test_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(client, email="performance_test-schema@example.com", username="performasch")
    workspace = await create_workspace(client, tokens["access_token"], slug="performance_test-schema-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="performance_test-schema-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_performance_test_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_performance_tests(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    assert "load_test_plan" in artifact
    assert "stress_test_plan" in artifact
    assert "performance_bottlenecks" in artifact
    assert "scaling_recommendations" in artifact
    assert "caching_recommendations" in artifact



async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(client, email="performance_test-meta@example.com", username="performamet")
    workspace = await create_workspace(client, tokens["access_token"], slug="performance_test-meta-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="performance_test-meta-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_performance_test_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_performance_tests(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None
    assert data["artifact"]["model_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(client, email="performance_test-history@example.com", username="performahst")
    workspace = await create_workspace(client, tokens["access_token"], slug="performance_test-hist-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="performance_test-hist-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_performance_test_pipeline(client, tokens["access_token"], requirement["id"])
    await run_performance_tests(client, tokens["access_token"], requirement["id"])
    await run_performance_tests(client, tokens["access_token"], requirement["id"])
    response = await client.get(f"/v1/agents/performance-tests/{requirement['id']}", headers=auth_headers(tokens["access_token"]))
    assert response.json()["total"] >= 2


async def test_required_counts_meet_minimums(client):
    _, tokens = await create_authenticated_user(client, email="performance_test-mins@example.com", username="performamin")
    workspace = await create_workspace(client, tokens["access_token"], slug="performance_test-min-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="performance_test-min-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_performance_test_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_performance_tests(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    assert len(artifact["load_test_plan"]) >= 5
    assert len(artifact["stress_test_plan"]) >= 3
    assert len(artifact["performance_bottlenecks"]) >= 3
    assert len(artifact["scaling_recommendations"]) >= 3
    assert len(artifact["caching_recommendations"]) >= 3
