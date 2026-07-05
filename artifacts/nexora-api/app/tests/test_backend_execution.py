from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_backend_execution,
    setup_backend_execution_pipeline,
)


async def test_run_backend_execution_success(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-run@example.com", username="ferun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["build_status"] == "success"
    assert data["artifact"] is not None


async def test_run_requires_backend_code_review_first(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-no-review@example.com", username="fenoreview"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-no-review-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-no-review-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    response = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_backend_execution_run(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-get-run@example.com", username="fegetrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-get-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-get-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(
        f"/v1/agents/backend-execution/runs/{run_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_backend_execution_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-get-art@example.com", username="fegetart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-art-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-art-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/backend-execution/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["artifact_json"]["execution_logs"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-list@example.com", username="felist"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-list-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-list-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    await run_backend_execution(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/backend-execution/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_artifact_has_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-md@example.com", username="femd"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-md-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-md-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    assert "Backend Execution Report" in created.json()["artifact"]["artifact_markdown"]


async def test_run_stores_executor_version(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-exec-ver@example.com", username="feexecver"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-ev-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-ev-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    assert created.json()["executor_version"] == "1.0.0"


async def test_run_stores_backend_v3_and_code_review_run_ids(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-link@example.com", username="felink"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_backend_execution_pipeline(
        client, tokens["access_token"], requirement["id"]
    )
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["backend_v3_run_id"] == pipeline["backend_v3_run"]["id"]
    assert data["backend_code_review_run_id"] == pipeline["backend_code_review_run"]["id"]


async def test_run_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-notfound@example.com", username="fenotfound"
    )
    response = await client.get(
        "/v1/agents/backend-execution/runs/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404


async def test_artifact_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-art-missing@example.com", username="feartmissing"
    )
    response = await client.get(
        "/v1/agents/backend-execution/artifacts/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404
