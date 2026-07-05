from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_sre_approval,
    setup_sre_approval_pipeline,
)


async def test_run_sre_approval_success(client):
    _, tokens = await create_authenticated_user(client, email="sre-run@example.com", username="srerun")
    workspace = await create_workspace(client, tokens["access_token"], slug="sre-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="sre-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_sre_approval_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_sre_approval(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_prerequisites(client):
    _, tokens = await create_authenticated_user(client, email="sre-nopre@example.com", username="srenopre")
    workspace = await create_workspace(client, tokens["access_token"], slug="sre-no-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="sre-no-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    response = await run_sre_approval(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_sre_approval_run(client):
    _, tokens = await create_authenticated_user(client, email="sre-get@example.com", username="sreget")
    workspace = await create_workspace(client, tokens["access_token"], slug="sre-get-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="sre-get-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_sre_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_sre_approval(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(f"/v1/agents/sre-approval/runs/{run_id}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_sre_approval_artifact(client):
    _, tokens = await create_authenticated_user(client, email="sre-art@example.com", username="sreart")
    workspace = await create_workspace(client, tokens["access_token"], slug="sre-art-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="sre-art-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_sre_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_sre_approval(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(f"/v1/agents/sre-approval/artifacts/{artifact_id}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["artifact_json"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(client, email="sre-list@example.com", username="srelist")
    workspace = await create_workspace(client, tokens["access_token"], slug="sre-list-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="sre-list-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_sre_approval_pipeline(client, tokens["access_token"], requirement["id"])
    await run_sre_approval(client, tokens["access_token"], requirement["id"])
    response = await client.get(f"/v1/agents/sre-approval/{requirement['id']}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_sre_status_present_in_artifact(client):
    _, tokens = await create_authenticated_user(client, email="sre-status@example.com", username="srestatus")
    workspace = await create_workspace(client, tokens["access_token"], slug="sre-status-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="sre-status-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_sre_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_sre_approval(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    assert artifact["sre_status"] in ("SRE_APPROVED", "SRE_APPROVED_WITH_WARNINGS", "SRE_REJECTED")
    for field in (
        "production_readiness_score",
        "availability_score",
        "security_score",
        "performance_score",
        "cost_score",
        "operational_readiness_score",
    ):
        assert 0 <= artifact[field] <= 100
