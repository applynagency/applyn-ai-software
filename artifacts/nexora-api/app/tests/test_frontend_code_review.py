from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_frontend_code_review,
    setup_frontend_code_review_pipeline,
)


async def test_run_frontend_code_review_success(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-run@example.com", username="fcrrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["review_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_frontend_v3_first(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-no-v3@example.com", username="fcrnov3"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-no-v3-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-no-v3-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    response = await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_frontend_code_review_run(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-get-run@example.com", username="fcrgetrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-get-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-get-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(
        f"/v1/agents/frontend-code-review/runs/{run_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_frontend_code_review_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-get-art@example.com", username="fcrgetart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-art-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-art-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/frontend-code-review/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["artifact_json"]["issues"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-list@example.com", username="fcrlist"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-list-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-list-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/frontend-code-review/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_artifact_has_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-md@example.com", username="fcrmd"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-md-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-md-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    assert "Frontend Code Review" in created.json()["artifact"]["artifact_markdown"]


async def test_run_stores_prompt_version(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-prompt@example.com", username="fcrprompt"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-pv-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-pv-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    assert created.json()["prompt_version"] == "1.0.0"


async def test_run_stores_frontend_v3_run_id(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-v3-link@example.com", username="fcrv3link"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fcr-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fcr-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_frontend_code_review_pipeline(
        client, tokens["access_token"], requirement["id"]
    )
    created = await run_frontend_code_review(client, tokens["access_token"], requirement["id"])
    assert created.json()["frontend_v3_run_id"] == pipeline["frontend_v3_run"]["id"]


async def test_run_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-notfound@example.com", username="fcrnotfound"
    )
    response = await client.get(
        "/v1/agents/frontend-code-review/runs/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404


async def test_artifact_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="fcr-art-missing@example.com", username="fcrartmissing"
    )
    response = await client.get(
        "/v1/agents/frontend-code-review/artifacts/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404
