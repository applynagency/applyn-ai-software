from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_backend_v2,
    setup_backend_v2_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-schema@example.com", username="bv2schema"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-schema-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-schema-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for key in (
        "file_structure",
        "router_files",
        "schema_files",
        "model_files",
        "repository_files",
        "service_files",
        "dependency_files",
        "middleware_files",
        "background_job_files",
        "integration_files",
        "configuration_files",
        "migration_files",
        "test_files",
        "infrastructure_files",
    ):
        assert key in artifact


async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-meta@example.com", username="bv2meta"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-meta-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-meta-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None
    assert data["artifact"]["model_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-history@example.com", username="bv2history"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-hist-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-hist-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    await run_backend_v2(client, tokens["access_token"], requirement["id"])
    await run_backend_v2(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/backend-v2/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.json()["total"] >= 2


async def test_completed_run_has_completed_at(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-complete@example.com", username="bv2complete"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-complete-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-complete-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    assert created.json()["completed_at"] is not None


async def test_router_files_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-routers@example.com", username="bv2routers"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-rt-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-rt-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    routers = created.json()["artifact"]["artifact_json"]["router_files"]
    assert len(routers) >= 10


async def test_schema_files_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-schemas@example.com", username="bv2schemas"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-sc-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-sc-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    schemas = created.json()["artifact"]["artifact_json"]["schema_files"]
    assert len(schemas) >= 10


async def test_model_files_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-models@example.com", username="bv2models"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-md-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-md-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    models = created.json()["artifact"]["artifact_json"]["model_files"]
    assert len(models) >= 10


async def test_repository_files_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-repos@example.com", username="bv2repos"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-repo-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-repo-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    repos = created.json()["artifact"]["artifact_json"]["repository_files"]
    assert len(repos) >= 10


async def test_service_files_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-services@example.com", username="bv2services"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-svc-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-svc-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    services = created.json()["artifact"]["artifact_json"]["service_files"]
    assert len(services) >= 10


async def test_middleware_files_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-middleware@example.com", username="bv2middleware"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-mw-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-mw-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    middleware = created.json()["artifact"]["artifact_json"]["middleware_files"]
    assert len(middleware) >= 5


async def test_integration_files_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-integrations@example.com", username="bv2integrations"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-int-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-int-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    integrations = created.json()["artifact"]["artifact_json"]["integration_files"]
    assert len(integrations) >= 5


async def test_test_files_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-tests@example.com", username="bv2tests"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-ts-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-ts-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v2(client, tokens["access_token"], requirement["id"])
    tests = created.json()["artifact"]["artifact_json"]["test_files"]
    assert len(tests) >= 10


async def test_run_with_explicit_backend_v1_run_id(client):
    _, tokens = await create_authenticated_user(
        client, email="bv2-explicit-v1@example.com", username="bv2explicitv1"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv2-explicit-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv2-explicit-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_backend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_backend_v2(
        client,
        tokens["access_token"],
        requirement["id"],
        backend_v1_run_id=pipeline["backend_v1_run"]["id"],
    )
    assert response.status_code == 201
    assert response.json()["backend_v1_run_id"] == pipeline["backend_v1_run"]["id"]
