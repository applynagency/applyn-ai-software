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


async def test_run_unit_test_generator_success(client):
    _, tokens = await create_authenticated_user(
        client, email="ut-run@example.com", username="utrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ut-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ut-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_qa_architect(client, tokens["access_token"], requirement["id"])
    response = await run_unit_tests(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_qa_architect_first(client):
    _, tokens = await create_authenticated_user(
        client, email="ut-no-qa@example.com", username="utnoqa"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ut-no-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ut-no-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    response = await run_unit_tests(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_unit_test_run(client):
    _, tokens = await create_authenticated_user(
        client, email="ut-get-run@example.com", username="utgetrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ut-get-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ut-get-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_qa_architect(client, tokens["access_token"], requirement["id"])
    created = await run_unit_tests(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(
        f"/v1/agents/unit-tests/runs/{run_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_unit_test_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="ut-get-art@example.com", username="utgetart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ut-art-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ut-art-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_qa_architect(client, tokens["access_token"], requirement["id"])
    created = await run_unit_tests(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/unit-tests/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["artifact_json"]["frontend_unit_test_specifications"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="ut-list@example.com", username="utlist"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ut-list-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ut-list-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_qa_architect(client, tokens["access_token"], requirement["id"])
    await run_unit_tests(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/unit-tests/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1
