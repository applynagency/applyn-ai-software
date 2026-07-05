from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_deployment,
    setup_deployment_pipeline,
)


async def test_post_run_returns_201(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-api-post@example.com", username="depapipost"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_deployment(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_get_runs_endpoint_returns_list(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-api-list@example.com", username="depapilist"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-list-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-list-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    await run_deployment(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/deployment/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert "items" in response.json()
    assert "total" in response.json()


async def test_artifact_endpoint_returns_json_and_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-api-art@example.com", username="depapiart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-art-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-art-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/deployment/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    body = response.json()
    assert response.status_code == 200
    assert body["artifact_json"]
    assert body["artifact_markdown"]
    assert body["deployment_status"] == "DEPLOYED"


async def test_success_response_includes_validation_score(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-api-score@example.com", username="depapiscore"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-score-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-score-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["validation_score"] is not None
    assert data["validation_score"] >= 80
    assert data["artifact"]["validation_score"] == data["validation_score"]


async def test_success_response_includes_deployed_status(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-api-status@example.com", username="depapistatus"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-status-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-status-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["status"] == "DEPLOYED"
    assert data["artifact"]["deployment_status"] == "DEPLOYED"


async def test_list_deployments_endpoint(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-api-deployments@example.com", username="depapideployments"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-deployments-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-deployments-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    await run_deployment(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        "/v1/deployments",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_get_deployment_by_id(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-api-get@example.com", username="depapiget"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-get-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-get-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    deployment_id = created.json()["id"]
    response = await client.get(
        f"/v1/deployments/{deployment_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == deployment_id
