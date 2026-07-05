from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_qa_architect,
    run_unit_tests,
    setup_qa_architect_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(
        client, email="ut-schema@example.com", username="utschema"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ut-schema-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ut-schema-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_qa_architect(client, tokens["access_token"], requirement["id"])
    created = await run_unit_tests(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for key in (
        "frontend_unit_test_specifications",
        "backend_unit_test_specifications",
        "mock_strategy",
        "test_fixtures",
        "coverage_targets",
    ):
        assert key in artifact


async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(
        client, email="ut-meta@example.com", username="utmeta"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ut-meta-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ut-meta-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_qa_architect(client, tokens["access_token"], requirement["id"])
    created = await run_unit_tests(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None
    assert data["artifact"]["model_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(
        client, email="ut-history@example.com", username="uthistory"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ut-hist-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ut-hist-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_qa_architect(client, tokens["access_token"], requirement["id"])
    await run_unit_tests(client, tokens["access_token"], requirement["id"])
    await run_unit_tests(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/unit-tests/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.json()["total"] >= 2


async def test_spec_and_fixture_counts_meet_minimums(client):
    _, tokens = await create_authenticated_user(
        client, email="ut-mins@example.com", username="utmins"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ut-min-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ut-min-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_qa_architect(client, tokens["access_token"], requirement["id"])
    created = await run_unit_tests(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    assert len(artifact["frontend_unit_test_specifications"]) >= 5
    assert len(artifact["backend_unit_test_specifications"]) >= 5
    assert len(artifact["test_fixtures"]) >= 3
