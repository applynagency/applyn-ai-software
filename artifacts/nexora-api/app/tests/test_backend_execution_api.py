from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_backend_execution,
    setup_backend_execution_pipeline,
)


async def test_post_run_returns_201(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-api-post@example.com", username="feapipost"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_get_runs_endpoint_returns_list(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-api-list@example.com", username="feapilist"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-list-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-list-api-proj"
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
    assert "items" in response.json()
    assert "total" in response.json()


async def test_artifact_endpoint_returns_json_and_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-api-art@example.com", username="feapiart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-art-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-art-api-proj"
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
    body = response.json()
    assert response.status_code == 200
    assert body["artifact_json"]
    assert body["artifact_markdown"]
    assert body["build_status"] is not None
