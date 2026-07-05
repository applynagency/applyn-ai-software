from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_frontend_v1,
    setup_frontend_v1_pipeline,
)


async def test_post_run_returns_201(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-api-post@example.com", username="fv1apipost"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_get_runs_endpoint_returns_list(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-api-list@example.com", username="fv1apilist"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-list-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-list-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/frontend-v1/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert "items" in response.json()
    assert "total" in response.json()


async def test_artifact_endpoint_returns_json_and_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-api-art@example.com", username="fv1apiart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-art-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-art-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/frontend-v1/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    body = response.json()
    assert response.status_code == 200
    assert body["artifact_json"]
    assert body["artifact_markdown"]
    assert body["validation_score"] is not None
