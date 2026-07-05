from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_infrastructure_architects,
    setup_infrastructure_architect_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(client, email="infrastructure_architect-schema@example.com", username="integratsch")
    workspace = await create_workspace(client, tokens["access_token"], slug="infrastructure_architect-schema-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="infrastructure_architect-schema-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_infrastructure_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_infrastructure_architects(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    assert "environments" in artifact
    assert "scaling_rules" in artifact
    assert "security_controls" in artifact
    assert "backup_recovery_plans" in artifact



async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(client, email="infrastructure_architect-meta@example.com", username="integratmet")
    workspace = await create_workspace(client, tokens["access_token"], slug="infrastructure_architect-meta-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="infrastructure_architect-meta-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_infrastructure_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_infrastructure_architects(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None
    assert data["artifact"]["model_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(client, email="infrastructure_architect-history@example.com", username="integrathst")
    workspace = await create_workspace(client, tokens["access_token"], slug="infrastructure_architect-hist-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="infrastructure_architect-hist-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_infrastructure_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_infrastructure_architects(client, tokens["access_token"], requirement["id"])
    await run_infrastructure_architects(client, tokens["access_token"], requirement["id"])
    response = await client.get(f"/v1/agents/infrastructure-architect/{requirement['id']}", headers=auth_headers(tokens["access_token"]))
    assert response.json()["total"] >= 2


async def test_required_counts_meet_minimums(client):
    _, tokens = await create_authenticated_user(client, email="infrastructure_architect-mins@example.com", username="integratmin")
    workspace = await create_workspace(client, tokens["access_token"], slug="infrastructure_architect-min-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="infrastructure_architect-min-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_infrastructure_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_infrastructure_architects(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    assert len(artifact["environments"]) >= 3
    assert len(artifact["scaling_rules"]) >= 3
    assert len(artifact["security_controls"]) >= 3
