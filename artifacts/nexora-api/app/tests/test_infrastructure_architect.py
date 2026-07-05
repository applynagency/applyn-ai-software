from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_infrastructure_architect,
    setup_infrastructure_architect_pipeline,
)


async def test_run_infrastructure_architect_success(client):
    _, tokens = await create_authenticated_user(client, email="infrastructure_architect-run@example.com", username="infrastrrun")
    workspace = await create_workspace(client, tokens["access_token"], slug="infrastructure_architect-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="infrastructure_architect-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_infrastructure_architect_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_infrastructure_architect(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_prerequisites(client):
    _, tokens = await create_authenticated_user(client, email="infrastructure_architect-nopre@example.com", username="infrastrnopre")
    workspace = await create_workspace(client, tokens["access_token"], slug="infrastructure_architect-no-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="infrastructure_architect-no-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    response = await run_infrastructure_architect(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_infrastructure_architect_run(client):
    _, tokens = await create_authenticated_user(client, email="infrastructure_architect-get@example.com", username="infrastrget")
    workspace = await create_workspace(client, tokens["access_token"], slug="infrastructure_architect-get-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="infrastructure_architect-get-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_infrastructure_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_infrastructure_architect(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(f"/v1/agents/infrastructure-architect/runs/{run_id}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_infrastructure_architect_artifact(client):
    _, tokens = await create_authenticated_user(client, email="infrastructure_architect-art@example.com", username="infrastrart")
    workspace = await create_workspace(client, tokens["access_token"], slug="infrastructure_architect-art-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="infrastructure_architect-art-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_infrastructure_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_infrastructure_architect(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(f"/v1/agents/infrastructure-architect/artifacts/{artifact_id}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["artifact_json"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(client, email="infrastructure_architect-list@example.com", username="infrastrlist")
    workspace = await create_workspace(client, tokens["access_token"], slug="infrastructure_architect-list-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="infrastructure_architect-list-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_infrastructure_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_infrastructure_architect(client, tokens["access_token"], requirement["id"])
    response = await client.get(f"/v1/agents/infrastructure-architect/{requirement['id']}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["total"] >= 1
