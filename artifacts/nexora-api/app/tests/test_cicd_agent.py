from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_cicd_agent,
    setup_cicd_agent_pipeline,
)


async def test_run_cicd_agent_success(client):
    _, tokens = await create_authenticated_user(client, email="cicd_agent-run@example.com", username="cicd_agerun")
    workspace = await create_workspace(client, tokens["access_token"], slug="cicd_agent-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="cicd_agent-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_cicd_agent_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_cicd_agent(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_prerequisites(client):
    _, tokens = await create_authenticated_user(client, email="cicd_agent-nopre@example.com", username="cicd_agenopre")
    workspace = await create_workspace(client, tokens["access_token"], slug="cicd_agent-no-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="cicd_agent-no-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    response = await run_cicd_agent(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_cicd_agent_run(client):
    _, tokens = await create_authenticated_user(client, email="cicd_agent-get@example.com", username="cicd_ageget")
    workspace = await create_workspace(client, tokens["access_token"], slug="cicd_agent-get-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="cicd_agent-get-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_cicd_agent_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_cicd_agent(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(f"/v1/agents/cicd/runs/{run_id}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_cicd_agent_artifact(client):
    _, tokens = await create_authenticated_user(client, email="cicd_agent-art@example.com", username="cicd_ageart")
    workspace = await create_workspace(client, tokens["access_token"], slug="cicd_agent-art-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="cicd_agent-art-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_cicd_agent_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_cicd_agent(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(f"/v1/agents/cicd/artifacts/{artifact_id}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["artifact_json"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(client, email="cicd_agent-list@example.com", username="cicd_agelist")
    workspace = await create_workspace(client, tokens["access_token"], slug="cicd_agent-list-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="cicd_agent-list-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_cicd_agent_pipeline(client, tokens["access_token"], requirement["id"])
    await run_cicd_agent(client, tokens["access_token"], requirement["id"])
    response = await client.get(f"/v1/agents/cicd/{requirement['id']}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["total"] >= 1
