from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_approval,
    setup_approval_pipeline,
)


async def test_post_run_returns_201(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-api-post@example.com", username="apprapipost"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_approval(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_get_runs_endpoint_returns_list(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-api-list@example.com", username="apprapilist"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-list-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-list-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    await run_approval(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/approval/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert "items" in response.json()
    assert "total" in response.json()


async def test_artifact_endpoint_returns_json_and_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-api-art@example.com", username="apprapiart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-art-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-art-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/approval/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    body = response.json()
    assert response.status_code == 200
    assert body["artifact_json"]
    assert body["artifact_markdown"]
    assert body["approval_status"] == "UNDER_REVIEW"


async def test_success_response_includes_validation_score(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-api-score@example.com", username="apprapiscore"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-score-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-score-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["validation_score"] is not None
    assert data["validation_score"] >= 80
    assert data["artifact"]["validation_score"] == data["validation_score"]


async def test_success_response_includes_under_review_status(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-api-status@example.com", username="apprapistatus"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-status-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-status-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["approval_status"] == "UNDER_REVIEW"
    assert data["artifact"]["approval_status"] == data["approval_status"]
