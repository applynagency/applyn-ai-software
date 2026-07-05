from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_docker_agent,
    setup_docker_agent_pipeline,
)


async def test_run_docker_agent_success(client):
    _, tokens = await create_authenticated_user(client, email="docker_agent-run@example.com", username="docker_arun")
    workspace = await create_workspace(client, tokens["access_token"], slug="docker_agent-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="docker_agent-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_docker_agent_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_docker_agent(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_prerequisites(client):
    _, tokens = await create_authenticated_user(client, email="docker_agent-nopre@example.com", username="docker_anopre")
    workspace = await create_workspace(client, tokens["access_token"], slug="docker_agent-no-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="docker_agent-no-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    response = await run_docker_agent(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_docker_agent_run(client):
    _, tokens = await create_authenticated_user(client, email="docker_agent-get@example.com", username="docker_aget")
    workspace = await create_workspace(client, tokens["access_token"], slug="docker_agent-get-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="docker_agent-get-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_docker_agent_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_docker_agent(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(f"/v1/agents/docker-agent/runs/{run_id}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_docker_agent_artifact(client):
    _, tokens = await create_authenticated_user(client, email="docker_agent-art@example.com", username="docker_aart")
    workspace = await create_workspace(client, tokens["access_token"], slug="docker_agent-art-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="docker_agent-art-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_docker_agent_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_docker_agent(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(f"/v1/agents/docker-agent/artifacts/{artifact_id}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["artifact_json"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(client, email="docker_agent-list@example.com", username="docker_alist")
    workspace = await create_workspace(client, tokens["access_token"], slug="docker_agent-list-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="docker_agent-list-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_docker_agent_pipeline(client, tokens["access_token"], requirement["id"])
    await run_docker_agent(client, tokens["access_token"], requirement["id"])
    response = await client.get(f"/v1/agents/docker-agent/{requirement['id']}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["total"] >= 1
