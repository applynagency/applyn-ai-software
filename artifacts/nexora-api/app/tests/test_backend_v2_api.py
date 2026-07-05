from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_backend_v2,
    setup_backend_v2_pipeline,
)


async def test_post_run_returns_201(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-api-post@example.com", username="bv2apipost"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_get_runs_endpoint_returns_list(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-api-list@example.com", username="bv2apilist"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-list-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-list-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    await run_backend_v2(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/backend-v2/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert "items" in response.json()
    assert "total" in response.json()


async def test_artifact_endpoint_returns_json_and_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-api-art@example.com", username="bv2apiart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-art-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-art-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/backend-v2/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    body = response.json()
    assert response.status_code == 200
    assert body["artifact_json"]
    assert body["artifact_markdown"]
    assert body["validation_score"] is not None


async def test_get_run_endpoint_returns_run_with_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-api-get@example.com", username="bv2apiget"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-get-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-get-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(
        f"/v1/agents/backend-v2/runs/{run_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["artifact"] is not None
