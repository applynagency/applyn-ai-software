from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_frontend_v1,
    setup_frontend_v1_pipeline,
)


async def test_run_frontend_v1_success(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-run@example.com", username="fv1run"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_frontend_architect_first(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-no-fa@example.com", username="fv1nofa"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-no-fa-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-no-fa-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    response = await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_frontend_v1_run(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-get-run@example.com", username="fv1getrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-get-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-get-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(
        f"/v1/agents/frontend-v1/runs/{run_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_frontend_v1_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-get-art@example.com", username="fv1getart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-art-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-art-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/frontend-v1/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["artifact_json"]["page_structure"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-list@example.com", username="fv1list"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-list-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-list-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/frontend-v1/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_artifact_has_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-md@example.com", username="fv1md"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-md-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-md-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    assert "Frontend Implementation Blueprint" in created.json()["artifact"]["artifact_markdown"]


async def test_run_stores_prompt_version(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-prompt@example.com", username="fv1prompt"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-pv-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-pv-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    assert created.json()["prompt_version"] == "1.0.0"


async def test_run_stores_frontend_architect_run_id(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-fa-link@example.com", username="fv1falink"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    assert created.json()["frontend_architect_run_id"] == pipeline["frontend_architect_run"]["id"]


async def test_run_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-notfound@example.com", username="fv1notfound"
    )
    response = await client.get(
        "/v1/agents/frontend-v1/runs/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404


async def test_artifact_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-art-missing@example.com", username="fv1artmissing"
    )
    response = await client.get(
        "/v1/agents/frontend-v1/artifacts/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404
