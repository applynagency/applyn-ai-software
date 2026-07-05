from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_qa_architect,
    setup_qa_architect_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(
        client, email="qa-schema@example.com", username="qaschema"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="qa-schema-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="qa-schema-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_qa_architect(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for key in (
        "test_strategy",
        "test_coverage_matrix",
        "risk_areas",
        "critical_user_journeys",
        "regression_areas",
        "acceptance_test_plan",
    ):
        assert key in artifact


async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(
        client, email="qa-meta@example.com", username="qameta"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="qa-meta-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="qa-meta-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_qa_architect(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None
    assert data["artifact"]["model_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(
        client, email="qa-history@example.com", username="qahistory"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="qa-hist-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="qa-hist-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_qa_architect(client, tokens["access_token"], requirement["id"])
    await run_qa_architect(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/qa-architect/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.json()["total"] >= 2


async def test_required_counts_meet_minimums(client):
    _, tokens = await create_authenticated_user(
        client, email="qa-mins@example.com", username="qamins"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="qa-min-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="qa-min-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_qa_architect(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    assert len(artifact["test_coverage_matrix"]) >= 10
    assert len(artifact["risk_areas"]) >= 5
    assert len(artifact["acceptance_test_plan"]) >= 5
    assert len(artifact["regression_areas"]) >= 5
