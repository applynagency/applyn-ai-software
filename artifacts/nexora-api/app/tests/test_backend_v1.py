from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_backend_v1,
    setup_backend_v1_pipeline,
)


async def test_run_backend_v1_success(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-run@example.com", username="bv1run"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_backend_v1(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_backend_architect_first(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-no-ba@example.com", username="bv1noba"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-no-ba-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-no-ba-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    response = await run_backend_v1(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_backend_v1_run(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-get-run@example.com", username="bv1getrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-get-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-get-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v1(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(
        f"/v1/agents/backend-v1/runs/{run_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_backend_v1_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-get-art@example.com", username="bv1getart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-art-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-art-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v1(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/backend-v1/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["artifact_json"]["api_specifications"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-list@example.com", username="bv1list"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-list-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-list-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    await run_backend_v1(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/backend-v1/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_artifact_has_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-md@example.com", username="bv1md"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-md-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-md-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v1(client, tokens["access_token"], requirement["id"])
    assert "Backend Implementation Specification" in created.json()["artifact"]["artifact_markdown"]


async def test_run_stores_prompt_version(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-prompt@example.com", username="bv1prompt"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-pv-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-pv-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v1(client, tokens["access_token"], requirement["id"])
    assert created.json()["prompt_version"] == "1.0.0"


async def test_run_stores_backend_architect_run_id(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-ba-link@example.com", username="bv1balink"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v1(client, tokens["access_token"], requirement["id"])
    assert created.json()["backend_architect_run_id"] == pipeline["backend_architect_run"]["id"]


async def test_run_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-notfound@example.com", username="bv1notfound"
    )
    response = await client.get(
        "/v1/agents/backend-v1/runs/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404


async def test_artifact_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-art-missing@example.com", username="bv1artmissing"
    )
    response = await client.get(
        "/v1/agents/backend-v1/artifacts/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404
