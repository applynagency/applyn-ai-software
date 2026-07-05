from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_backend_code_review,
    setup_backend_code_review_pipeline,
)


async def test_run_backend_code_review_success(client):
    _, tokens = await create_authenticated_user(
        client, email="bcr-run@example.com", username="bcrrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bcr-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bcr-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_backend_code_review(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["review_score"] is not None
    assert data["artifact"] is not None


async def test_get_backend_code_review_run(client):
    _, tokens = await create_authenticated_user(
        client, email="bcr-get-run@example.com", username="bcrgetrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bcr-get-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bcr-get-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_code_review(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(
        f"/v1/agents/backend-code-review/runs/{run_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_backend_code_review_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="bcr-get-art@example.com", username="bcrgetart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bcr-art-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bcr-art-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_code_review_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_code_review(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/backend-code-review/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["artifact_json"]["issues"]
