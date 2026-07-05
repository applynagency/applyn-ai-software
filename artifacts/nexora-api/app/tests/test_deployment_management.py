from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_deployment,
    setup_deployment_pipeline,
)


async def test_get_deployment_logs(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-logs@example.com", username="deplogs"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-logs-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-logs-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    deployment_id = created.json()["id"]
    response = await client.get(
        f"/v1/deployments/{deployment_id}/logs",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert len(body["items"]) >= 1
    assert body["items"][0]["message"]


async def test_deployment_logs_include_azure_messages(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-logs-azure@example.com", username="deplogsazure"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-logs-az-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-logs-az-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/deployments/{created.json()['id']}/logs",
        headers=auth_headers(tokens["access_token"]),
    )
    messages = " ".join(item["message"] for item in response.json()["items"])
    assert "Azure" in messages or "App Service" in messages


async def test_rollback_transitions_status(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-rollback@example.com", username="deprollback"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-rb-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-rb-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    deployment_id = created.json()["id"]
    assert created.json()["status"] == "DEPLOYED"

    rollback_response = await client.post(
        f"/v1/deployments/{deployment_id}/rollback",
        headers=auth_headers(tokens["access_token"]),
    )
    assert rollback_response.status_code == 200
    data = rollback_response.json()
    assert data["status"] == "ROLLED_BACK"
    assert data["rollback_available"] is False
    assert data["live_url"].endswith(".applyn.app")


async def test_rollback_not_allowed_when_not_deployed(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-rb-invalid@example.com", username="deprbinvalid"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-rb-inv-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-rb-inv-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    deployment_id = created.json()["id"]
    await client.post(
        f"/v1/deployments/{deployment_id}/rollback",
        headers=auth_headers(tokens["access_token"]),
    )
    second_rollback = await client.post(
        f"/v1/deployments/{deployment_id}/rollback",
        headers=auth_headers(tokens["access_token"]),
    )
    assert second_rollback.status_code == 422


async def test_delete_deployment_returns_204(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-delete@example.com", username="depdelete"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-del-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-del-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    deployment_id = created.json()["id"]
    response = await client.delete(
        f"/v1/deployments/{deployment_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 204


async def test_deleted_deployment_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-delete-gone@example.com", username="depdeletegone"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-del-gone-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-del-gone-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    deployment_id = created.json()["id"]
    await client.delete(
        f"/v1/deployments/{deployment_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    response = await client.get(
        f"/v1/deployments/{deployment_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404


async def test_rollback_appends_logs(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-rb-logs@example.com", username="deprblogs"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-rb-logs-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-rb-logs-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    deployment_id = created.json()["id"]
    logs_before = await client.get(
        f"/v1/deployments/{deployment_id}/logs",
        headers=auth_headers(tokens["access_token"]),
    )
    before_count = logs_before.json()["total"]
    await client.post(
        f"/v1/deployments/{deployment_id}/rollback",
        headers=auth_headers(tokens["access_token"]),
    )
    logs_after = await client.get(
        f"/v1/deployments/{deployment_id}/logs",
        headers=auth_headers(tokens["access_token"]),
    )
    assert logs_after.json()["total"] > before_count


async def test_list_deployments_after_delete_excludes_removed(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-list-del@example.com", username="deplistdel"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-list-del-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-list-del-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    deployment_id = created.json()["id"]
    before = await client.get("/v1/deployments", headers=auth_headers(tokens["access_token"]))
    before_total = before.json()["total"]
    await client.delete(
        f"/v1/deployments/{deployment_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    after = await client.get("/v1/deployments", headers=auth_headers(tokens["access_token"]))
    assert after.json()["total"] == before_total - 1
