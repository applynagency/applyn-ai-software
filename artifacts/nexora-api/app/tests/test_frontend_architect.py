from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_frontend_architect,
    setup_frontend_architect_pipeline,
)


async def test_run_frontend_architect_success(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-run@example.com", username="farun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_uiux_first(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-no-uiux@example.com", username="fanouiux"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-no-uiux-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-no-uiux-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    response = await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_frontend_architect_run(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-get-run@example.com", username="fagetrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-get-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-get-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(
        f"/v1/agents/frontend-architect/runs/{run_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_frontend_architect_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-get-art@example.com", username="fagetart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-art-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-art-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/frontend-architect/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["artifact_json"]["page_architecture"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-list@example.com", username="falist"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-list-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-list-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/frontend-architect/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_artifact_has_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-md@example.com", username="famd"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-md-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-md-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    assert "Frontend Architecture Blueprint" in created.json()["artifact"]["artifact_markdown"]


async def test_run_stores_prompt_version(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-prompt@example.com", username="faprompt"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-pv-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-pv-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    assert created.json()["prompt_version"] == "1.0.0"


async def test_run_stores_uiux_run_id(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-uiux-link@example.com", username="fauiuxlink"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    assert created.json()["uiux_run_id"] == pipeline["uiux_run"]["id"]


async def test_run_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-notfound@example.com", username="fanotfound"
    )
    response = await client.get(
        "/v1/agents/frontend-architect/runs/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404


async def test_artifact_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-art-missing@example.com", username="faartmissing"
    )
    response = await client.get(
        "/v1/agents/frontend-architect/artifacts/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404
