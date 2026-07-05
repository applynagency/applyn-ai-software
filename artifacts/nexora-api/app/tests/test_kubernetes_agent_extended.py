from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_kubernetes_agents,
    setup_kubernetes_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(client, email="k8s-schema@example.com", username="k8sschema")
    workspace = await create_workspace(client, tokens["access_token"], slug="k8s-schema-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="k8s-schema-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_kubernetes_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_kubernetes_agents(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for field in ("deployments", "services", "ingresses", "hpas", "configmaps_secrets", "network_policies", "environment_overlays"):
        assert field in artifact


async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(client, email="k8s-meta@example.com", username="k8smeta")
    workspace = await create_workspace(client, tokens["access_token"], slug="k8s-meta-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="k8s-meta-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_kubernetes_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_kubernetes_agents(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None
    assert data["artifact"]["model_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(client, email="k8s-history@example.com", username="k8shistory")
    workspace = await create_workspace(client, tokens["access_token"], slug="k8s-hist-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="k8s-hist-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_kubernetes_pipeline(client, tokens["access_token"], requirement["id"])
    await run_kubernetes_agents(client, tokens["access_token"], requirement["id"])
    await run_kubernetes_agents(client, tokens["access_token"], requirement["id"])
    response = await client.get(f"/v1/agents/kubernetes/{requirement['id']}", headers=auth_headers(tokens["access_token"]))
    assert response.json()["total"] >= 2


async def test_minimum_manifest_counts_met(client):
    _, tokens = await create_authenticated_user(client, email="k8s-mins@example.com", username="k8smins")
    workspace = await create_workspace(client, tokens["access_token"], slug="k8s-min-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="k8s-min-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_kubernetes_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_kubernetes_agents(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    assert len(artifact["deployments"]) >= 3
    assert len(artifact["services"]) >= 3
    assert len(artifact["ingresses"]) >= 1
    assert len(artifact["hpas"]) >= 1
    assert len(artifact["configmaps_secrets"]) >= 3
