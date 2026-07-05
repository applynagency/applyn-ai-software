from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_kubernetes_agent,
    setup_kubernetes_pipeline,
)


async def test_run_kubernetes_agent_success(client):
    _, tokens = await create_authenticated_user(client, email="k8s-run@example.com", username="k8srun")
    workspace = await create_workspace(client, tokens["access_token"], slug="k8s-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="k8s-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_kubernetes_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_kubernetes_agent(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_prerequisites(client):
    _, tokens = await create_authenticated_user(client, email="k8s-nopre@example.com", username="k8snopre")
    workspace = await create_workspace(client, tokens["access_token"], slug="k8s-no-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="k8s-no-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    response = await run_kubernetes_agent(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_kubernetes_run(client):
    _, tokens = await create_authenticated_user(client, email="k8s-get@example.com", username="k8sget")
    workspace = await create_workspace(client, tokens["access_token"], slug="k8s-get-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="k8s-get-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_kubernetes_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_kubernetes_agent(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(f"/v1/agents/kubernetes/runs/{run_id}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_kubernetes_artifact(client):
    _, tokens = await create_authenticated_user(client, email="k8s-art@example.com", username="k8sart")
    workspace = await create_workspace(client, tokens["access_token"], slug="k8s-art-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="k8s-art-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_kubernetes_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_kubernetes_agent(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(f"/v1/agents/kubernetes/artifacts/{artifact_id}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["artifact_json"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(client, email="k8s-list@example.com", username="k8slist")
    workspace = await create_workspace(client, tokens["access_token"], slug="k8s-list-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="k8s-list-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_kubernetes_pipeline(client, tokens["access_token"], requirement["id"])
    await run_kubernetes_agent(client, tokens["access_token"], requirement["id"])
    response = await client.get(f"/v1/agents/kubernetes/{requirement['id']}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["total"] >= 1
