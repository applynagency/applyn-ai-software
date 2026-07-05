from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_observability_agents,
    setup_observability_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(client, email="obs-schema@example.com", username="obsschema")
    workspace = await create_workspace(client, tokens["access_token"], slug="obs-schema-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="obs-schema-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_observability_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_observability_agents(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for field in ("prometheus_configuration", "logging_architecture", "tracing_architecture", "grafana_dashboards", "alert_rules", "logging_flows", "slo_definitions"):
        assert field in artifact


async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(client, email="obs-meta@example.com", username="obsmeta")
    workspace = await create_workspace(client, tokens["access_token"], slug="obs-meta-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="obs-meta-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_observability_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_observability_agents(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(client, email="obs-history@example.com", username="obshistory")
    workspace = await create_workspace(client, tokens["access_token"], slug="obs-hist-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="obs-hist-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_observability_pipeline(client, tokens["access_token"], requirement["id"])
    await run_observability_agents(client, tokens["access_token"], requirement["id"])
    await run_observability_agents(client, tokens["access_token"], requirement["id"])
    response = await client.get(f"/v1/agents/observability/{requirement['id']}", headers=auth_headers(tokens["access_token"]))
    assert response.json()["total"] >= 2


async def test_minimum_observability_counts_met(client):
    _, tokens = await create_authenticated_user(client, email="obs-mins@example.com", username="obsmins")
    workspace = await create_workspace(client, tokens["access_token"], slug="obs-min-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="obs-min-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_observability_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_observability_agents(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    assert len(artifact["alert_rules"]) >= 5
    assert len(artifact["grafana_dashboards"]) >= 3
    assert len(artifact["slo_definitions"]) >= 3
    assert len(artifact["logging_flows"]) >= 3
