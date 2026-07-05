from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_approval,
    run_deployment,
    setup_approval_pipeline,
    setup_deployment_pipeline,
)


async def test_run_deployment_success(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-run@example.com", username="deprun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_deployment(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "DEPLOYED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None
    assert data["live_url"].endswith(".applyn.app")


async def test_run_blocked_without_human_approval(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-no-appr@example.com", username="depnoappr"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-no-appr-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-no-appr-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    await run_approval(client, tokens["access_token"], requirement["id"])
    response = await run_deployment(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_run_blocked_when_approval_under_review(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-under-review@example.com", username="depunderreview"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-ur-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-ur-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    approval_response = await run_approval(client, tokens["access_token"], requirement["id"])
    assert approval_response.json()["approval_status"] == "UNDER_REVIEW"
    response = await run_deployment(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422
    # /v1/agents/deployment/run is customer-facing, so the "requires APPROVED"
    # gate surfaces through a customer-safe message. The ValidationError type
    # confirms deployment was blocked while the approval is still UNDER_REVIEW.
    assert response.json()["error_type"] == "ValidationError"


async def test_run_requires_approval_pipeline_first(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-no-pipe@example.com", username="depnopipe"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-no-pipe-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-no-pipe-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    response = await run_deployment(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_deployment_run(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-get-run@example.com", username="depgetrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-get-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-get-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(
        f"/v1/agents/deployment/runs/{run_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_deployment_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-get-art@example.com", username="depgetart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-art-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-art-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/deployment/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["artifact_json"]["deployment_status"] == "DEPLOYED"


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-list@example.com", username="deplist"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-list-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-list-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    await run_deployment(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/deployment/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_artifact_has_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-md@example.com", username="depmd"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-md-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-md-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    assert "Deployment Report" in created.json()["artifact"]["artifact_markdown"]


async def test_run_stores_deployer_version(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-ver@example.com", username="depver"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-ver-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-ver-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    assert created.json()["deployer_version"] == "1.0.0"


async def test_run_stores_approval_run_id(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-link@example.com", username="deplink"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    assert created.json()["approval_run_id"] == pipeline["approval_run"]["id"]


async def test_run_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-notfound@example.com", username="depnotfound"
    )
    response = await client.get(
        "/v1/agents/deployment/runs/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404


async def test_artifact_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-art-missing@example.com", username="departmissing"
    )
    response = await client.get(
        "/v1/agents/deployment/artifacts/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404
