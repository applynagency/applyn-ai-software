from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_qa_approval,
    setup_qa_approval_pipeline,
)


async def test_run_qa_approval_success(client):
    _, tokens = await create_authenticated_user(client, email="qa_approval-run@example.com", username="qa_approrun")
    workspace = await create_workspace(client, tokens["access_token"], slug="qa_approval-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="qa_approval-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_qa_approval_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_qa_approval(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_prerequisites(client):
    _, tokens = await create_authenticated_user(client, email="qa_approval-no-pre@example.com", username="qa_appronop")
    workspace = await create_workspace(client, tokens["access_token"], slug="qa_approval-no-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="qa_approval-no-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    response = await run_qa_approval(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_qa_approval_run(client):
    _, tokens = await create_authenticated_user(client, email="qa_approval-get@example.com", username="qa_approget")
    workspace = await create_workspace(client, tokens["access_token"], slug="qa_approval-get-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="qa_approval-get-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_qa_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_qa_approval(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(f"/v1/agents/qa-approvals/runs/{run_id}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_qa_approval_artifact(client):
    _, tokens = await create_authenticated_user(client, email="qa_approval-artifact@example.com", username="qa_approart")
    workspace = await create_workspace(client, tokens["access_token"], slug="qa_approval-art-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="qa_approval-art-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_qa_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_qa_approval(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(f"/v1/agents/qa-approvals/artifacts/{artifact_id}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["artifact_json"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(client, email="qa_approval-list@example.com", username="qa_approlst")
    workspace = await create_workspace(client, tokens["access_token"], slug="qa_approval-list-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="qa_approval-list-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_qa_approval_pipeline(client, tokens["access_token"], requirement["id"])
    await run_qa_approval(client, tokens["access_token"], requirement["id"])
    response = await client.get(f"/v1/agents/qa-approvals/{requirement['id']}", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["total"] >= 1
