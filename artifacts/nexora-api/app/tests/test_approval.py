from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_approval,
    setup_approval_pipeline,
)


async def test_run_approval_success(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-run@example.com", username="apprrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_approval(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["approval_status"] == "UNDER_REVIEW"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_fullstack_assembly_first(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-no-fsa@example.com", username="apprnofsa"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-no-fsa-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-no-fsa-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    response = await run_approval(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_approval_run(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-get-run@example.com", username="apprgetrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-get-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-get-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(
        f"/v1/agents/approval/runs/{run_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_approval_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-get-art@example.com", username="apprgetart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-art-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-art-proj"
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
    assert response.status_code == 200
    assert response.json()["artifact_json"]["review_checklist"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-list@example.com", username="apprlist"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-list-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-list-proj"
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
    assert response.json()["total"] >= 1


async def test_artifact_has_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-md@example.com", username="apprmd"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-md-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-md-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    assert "Approval Workflow Package" in created.json()["artifact"]["artifact_markdown"]


async def test_run_stores_processor_version(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-ver@example.com", username="apprver"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-ver-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-ver-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    assert created.json()["processor_version"] == "1.0.0"


async def test_run_stores_fullstack_assembly_run_id(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-link@example.com", username="apprlink"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    assert created.json()["fullstack_assembly_run_id"] == pipeline["fullstack_assembly_run"]["id"]


async def test_run_stores_recommendation(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-rec@example.com", username="apprrec"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-rec-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-rec-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    assert created.json()["recommendation"] in ("APPROVE", "REVIEW", "REJECT")


async def test_run_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-notfound@example.com", username="apprnotfound"
    )
    response = await client.get(
        "/v1/agents/approval/runs/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404


async def test_artifact_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-art-missing@example.com", username="apprartmissing"
    )
    response = await client.get(
        "/v1/agents/approval/artifacts/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404
