from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_frontend_v2,
    setup_frontend_v2_pipeline,
)


async def test_run_frontend_v2_success(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-run@example.com", username="fv2run"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_frontend_v1_first(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-no-v1@example.com", username="fv2nov1"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-no-v1-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-no-v1-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    response = await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_frontend_v2_run(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-get-run@example.com", username="fv2getrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-get-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-get-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(
        f"/v1/agents/frontend-v2/runs/{run_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_frontend_v2_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-get-art@example.com", username="fv2getart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-art-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-art-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/frontend-v2/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["artifact_json"]["page_files"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-list@example.com", username="fv2list"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-list-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-list-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/frontend-v2/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_artifact_has_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-md@example.com", username="fv2md"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-md-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-md-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    assert "Frontend File-Level Specifications" in created.json()["artifact"]["artifact_markdown"]


async def test_run_stores_prompt_version(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-prompt@example.com", username="fv2prompt"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-pv-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-pv-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    assert created.json()["prompt_version"] == "1.0.0"


async def test_run_stores_frontend_v1_run_id(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-v1-link@example.com", username="fv2v1link"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    assert created.json()["frontend_v1_run_id"] == pipeline["frontend_v1_run"]["id"]


async def test_run_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-notfound@example.com", username="fv2notfound"
    )
    response = await client.get(
        "/v1/agents/frontend-v2/runs/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404


async def test_artifact_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-art-missing@example.com", username="fv2artmissing"
    )
    response = await client.get(
        "/v1/agents/frontend-v2/artifacts/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404
