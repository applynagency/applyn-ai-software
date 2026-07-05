from unittest.mock import AsyncMock, patch

from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    login_user,
    mock_product_owner_output,
    register_user,
)


async def test_auth_me_endpoint(client):
    user, tokens = await create_authenticated_user(
        client, email="me@example.com", username="meuser"
    )
    response = await client.get("/v1/auth/me", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["email"] == user["email"]


async def test_refresh_token(client):
    await register_user(client, email="refresh@example.com", username="refreshuser")
    tokens = await login_user(client, email="refresh@example.com")
    response = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_create_and_list_workspaces(client):
    _, tokens = await create_authenticated_user(
        client, email="ws@example.com", username="wsuser"
    )
    await create_workspace(client, tokens["access_token"], name="Main", slug="main")
    response = await client.get("/v1/workspaces", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_get_workspace(client):
    _, tokens = await create_authenticated_user(
        client, email="getws@example.com", username="getwsuser"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="get-ws")
    response = await client.get(
        f"/v1/workspaces/{workspace['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200


async def test_update_workspace(client):
    _, tokens = await create_authenticated_user(
        client, email="updws@example.com", username="updwsuser"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="upd-ws")
    response = await client.patch(
        f"/v1/workspaces/{workspace['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"description": "Updated"},
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Updated"


async def test_delete_workspace(client):
    _, tokens = await create_authenticated_user(
        client, email="delws@example.com", username="delwsuser"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="del-ws")
    response = await client.delete(
        f"/v1/workspaces/{workspace['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 204


async def test_create_and_list_projects(client):
    _, tokens = await create_authenticated_user(
        client, email="proj@example.com", username="projuser"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="proj-ws")
    await create_project(client, tokens["access_token"], workspace_id=workspace["id"])
    response = await client.get("/v1/projects", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_get_project(client):
    _, tokens = await create_authenticated_user(
        client, email="getproj@example.com", username="getprojuser"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="get-proj-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="get-proj"
    )
    response = await client.get(
        f"/v1/projects/{project['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200


async def test_submit_and_list_requirements(client):
    _, tokens = await create_authenticated_user(
        client, email="req@example.com", username="requser"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="req-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="req-proj"
    )
    await create_requirement(client, tokens["access_token"], project_id=project["id"])
    response = await client.get(
        f"/v1/requirements?project_id={project['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1


async def test_get_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="getreq@example.com", username="getrequser"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="get-req-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="get-req-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    response = await client.get(
        f"/v1/requirements/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200


async def test_update_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="updreq@example.com", username="updrequser"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="upd-req-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="upd-req-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    response = await client.patch(
        f"/v1/requirements/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
        json={"title": "Updated title"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated title"


async def test_product_owner_agent_run(client):
    _, tokens = await create_authenticated_user(
        client, email="agent@example.com", username="agentuser"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="agent-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="agent-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )

    mock_output = mock_product_owner_output(
        project_summary="Generated summary",
        total_story_points=5,
    )
    with patch(
        "app.workflows.engine.AgentWorkflowEngine._dispatch_agent",
        new=AsyncMock(return_value=(mock_output, 250)),
    ):
        response = await client.post(
            "/v1/agents/product-owner/run",
            headers=auth_headers(tokens["access_token"]),
            json={"requirement_id": requirement["id"]},
        )
    assert response.status_code == 202
    assert response.json()["status"] == "completed"


async def test_get_agent_run(client):
    _, tokens = await create_authenticated_user(
        client, email="getrun@example.com", username="getrunuser"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="getrun-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="getrun-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )

    mock_output = mock_product_owner_output(
        project_summary="Run summary",
        total_story_points=8,
        estimated_sprints=2,
    )
    with patch(
        "app.workflows.engine.AgentWorkflowEngine._dispatch_agent",
        new=AsyncMock(return_value=(mock_output, 300)),
    ):
        created = await client.post(
            "/v1/agents/product-owner/run",
            headers=auth_headers(tokens["access_token"]),
            json={"requirement_id": requirement["id"]},
        )
    run_id = created.json()["id"]
    response = await client.get(
        f"/v1/agents/runs/{run_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == run_id
