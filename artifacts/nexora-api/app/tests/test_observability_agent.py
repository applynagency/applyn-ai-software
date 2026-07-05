from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_observability_agent,
    setup_observability_pipeline,
)


async def test_run_observability_agent_success(client):
    _, tokens = await create_authenticated_user(client, email="obs-run@example.com", username="obsrun")
    workspace = await create_workspace(client, tokens["access_token"], slug="obs-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="obs-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_observability_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_observability_agent(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_prerequisites(client):
    _, tokens = await create_authenticated_user(client, email="obs-nopre@example.com", username="obsnopre")
    workspace = await create_workspace(client, tokens["access_token"], slug="obs-no-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="obs-no-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    response = await run_observability_agent(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_observability_run(client):
    _, tokens = await create_authenticated_user(client, email="obs-get@example.com", username="obsget")
    workspace = await create_workspace(client, tokens["access_token"], slug="obs-get-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="obs-get-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_observability_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_observability_agent(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(f"/v1/agents/observability/runs/{run_id}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_observability_artifact(client):
    _, tokens = await create_authenticated_user(client, email="obs-art@example.com", username="obsart")
    workspace = await create_workspace(client, tokens["access_token"], slug="obs-art-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="obs-art-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_observability_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_observability_agent(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(f"/v1/agents/observability/artifacts/{artifact_id}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["artifact_json"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(client, email="obs-list@example.com", username="obslist")
    workspace = await create_workspace(client, tokens["access_token"], slug="obs-list-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="obs-list-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_observability_pipeline(client, tokens["access_token"], requirement["id"])
    await run_observability_agent(client, tokens["access_token"], requirement["id"])
    response = await client.get(f"/v1/agents/observability/{requirement['id']}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["total"] >= 1
