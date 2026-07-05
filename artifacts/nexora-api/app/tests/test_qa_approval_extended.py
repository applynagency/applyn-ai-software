from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_qa_approval,
    setup_qa_approval_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(client, email="qa_approval-schema@example.com", username="qa_approsch")
    workspace = await create_workspace(client, tokens["access_token"], slug="qa_approval-schema-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="qa_approval-schema-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_qa_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_qa_approval(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    assert "qa_status" in artifact
    assert "quality_score" in artifact
    assert "findings" in artifact
    assert "warnings" in artifact
    assert "recommendation" in artifact



async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(client, email="qa_approval-meta@example.com", username="qa_appromet")
    workspace = await create_workspace(client, tokens["access_token"], slug="qa_approval-meta-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="qa_approval-meta-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_qa_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_qa_approval(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None
    assert data["artifact"]["model_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(client, email="qa_approval-history@example.com", username="qa_approhst")
    workspace = await create_workspace(client, tokens["access_token"], slug="qa_approval-hist-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="qa_approval-hist-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_qa_approval_pipeline(client, tokens["access_token"], requirement["id"])
    await run_qa_approval(client, tokens["access_token"], requirement["id"])
    await run_qa_approval(client, tokens["access_token"], requirement["id"])
    response = await client.get(f"/v1/agents/qa-approvals/{requirement['id']}", headers=auth_headers(tokens["access_token"]))
    assert response.json()["total"] >= 2


async def test_required_counts_meet_minimums(client):
    _, tokens = await create_authenticated_user(client, email="qa_approval-mins@example.com", username="qa_appromin")
    workspace = await create_workspace(client, tokens["access_token"], slug="qa_approval-min-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="qa_approval-min-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_qa_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_qa_approval(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    assert len(artifact["findings"]) >= 1
