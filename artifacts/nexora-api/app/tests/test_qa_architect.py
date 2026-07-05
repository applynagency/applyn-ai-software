from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_qa_architect,
    setup_qa_architect_pipeline,
)


async def test_run_qa_architect_success(client):
    _, tokens = await create_authenticated_user(
        client, email="qa-run@example.com", username="qarun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="qa-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="qa-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_qa_architect(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_execution_prerequisites(client):
    _, tokens = await create_authenticated_user(
        client, email="qa-no-prereq@example.com", username="qanoprereq"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="qa-no-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="qa-no-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    response = await run_qa_architect(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_qa_architect_run(client):
    _, tokens = await create_authenticated_user(
        client, email="qa-get-run@example.com", username="qagetrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="qa-get-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="qa-get-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_qa_architect(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(
        f"/v1/agents/qa-architect/runs/{run_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_qa_architect_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="qa-get-art@example.com", username="qagetart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="qa-art-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="qa-art-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_qa_architect(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/qa-architect/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["artifact_json"]["test_coverage_matrix"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="qa-list@example.com", username="qalist"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="qa-list-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="qa-list-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_qa_architect(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/qa-architect/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_artifact_has_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="qa-md@example.com", username="qamd"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="qa-md-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="qa-md-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_qa_architect(client, tokens["access_token"], requirement["id"])
    assert "QA Architecture Blueprint" in created.json()["artifact"]["artifact_markdown"]


async def test_run_stores_prompt_version(client):
    _, tokens = await create_authenticated_user(
        client, email="qa-prompt@example.com", username="qaprompt"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="qa-pr-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="qa-pr-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_qa_architect(client, tokens["access_token"], requirement["id"])
    assert created.json()["prompt_version"] == "1.0.0"


async def test_run_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="qa-notfound@example.com", username="qanotfound"
    )
    response = await client.get(
        "/v1/agents/qa-architect/runs/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404
