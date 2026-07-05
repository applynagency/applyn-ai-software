from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_backend_v2,
    setup_backend_v2_pipeline,
)


async def test_run_backend_v2_success(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-run@example.com", username="bv2run"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_backend_v1_first(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-no-v1@example.com", username="bv2nov1"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-no-v1-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-no-v1-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    response = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_backend_v2_run(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-get-run@example.com", username="bv2getrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-get-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-get-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(
        f"/v1/agents/backend-v2/runs/{run_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_backend_v2_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-get-art@example.com", username="bv2getart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-art-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-art-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/backend-v2/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["artifact_json"]["router_files"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-list@example.com", username="bv2list"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-list-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-list-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    await run_backend_v2(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/backend-v2/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_artifact_has_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-md@example.com", username="bv2md"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-md-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-md-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    assert "Backend File-Level Specifications" in created.json()["artifact"]["artifact_markdown"]


async def test_run_stores_prompt_version(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-prompt@example.com", username="bv2prompt"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-pv-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-pv-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    assert created.json()["prompt_version"] == "1.0.0"


async def test_run_stores_backend_v1_run_id(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-v1-link@example.com", username="bv2v1link"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    assert created.json()["backend_v1_run_id"] == pipeline["backend_v1_run"]["id"]


async def test_run_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-notfound@example.com", username="bv2notfound"
    )
    response = await client.get(
        "/v1/agents/backend-v2/runs/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404


async def test_artifact_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-art-missing@example.com", username="bv2artmissing"
    )
    response = await client.get(
        "/v1/agents/backend-v2/artifacts/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404
