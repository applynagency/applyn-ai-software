from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_backend_v1,
    setup_backend_v1_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-schema@example.com", username="bv1schema"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-schema-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-schema-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v1(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for key in (
        "service_specifications",
        "repository_specifications",
        "api_specifications",
        "database_model_specifications",
        "authentication_specifications",
        "authorization_specifications",
        "validation_specifications",
        "background_job_specifications",
        "integration_specifications",
        "folder_structure",
        "module_breakdown",
        "implementation_guidelines",
    ):
        assert key in artifact


async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-meta@example.com", username="bv1meta"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-meta-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-meta-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v1(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None
    assert data["artifact"]["model_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-history@example.com", username="bv1history"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-hist-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-hist-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    await run_backend_v1(client, tokens["access_token"], requirement["id"])
    await run_backend_v1(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/backend-v1/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.json()["total"] >= 2


async def test_completed_run_has_completed_at(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-complete@example.com", username="bv1complete"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-complete-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-complete-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v1(client, tokens["access_token"], requirement["id"])
    assert created.json()["completed_at"] is not None


async def test_service_specifications_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-services@example.com", username="bv1services"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-svc-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-svc-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v1(client, tokens["access_token"], requirement["id"])
    services = created.json()["artifact"]["artifact_json"]["service_specifications"]
    assert len(services) >= 10


async def test_repository_specifications_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-repos@example.com", username="bv1repos"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-repo-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-repo-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v1(client, tokens["access_token"], requirement["id"])
    repos = created.json()["artifact"]["artifact_json"]["repository_specifications"]
    assert len(repos) >= 10


async def test_api_specifications_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-apis@example.com", username="bv1apis"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v1(client, tokens["access_token"], requirement["id"])
    apis = created.json()["artifact"]["artifact_json"]["api_specifications"]
    assert len(apis) >= 10


async def test_database_models_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-models@example.com", username="bv1models"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-model-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-model-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v1(client, tokens["access_token"], requirement["id"])
    models = created.json()["artifact"]["artifact_json"]["database_model_specifications"]
    assert len(models) >= 10


async def test_user_roles_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-roles@example.com", username="bv1roles"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-role-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-role-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v1(client, tokens["access_token"], requirement["id"])
    roles = created.json()["artifact"]["artifact_json"]["authorization_specifications"]["roles"]
    assert len(roles) >= 3


async def test_run_with_explicit_backend_architect_run_id(client):
    _, tokens = await create_authenticated_user(
        client, email="bv1-explicit-ba@example.com", username="bv1explicitba"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-explicit-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-explicit-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_backend_v1(
        client,
        tokens["access_token"],
        requirement["id"],
        backend_architect_run_id=pipeline["backend_architect_run"]["id"],
    )
    assert response.status_code == 201
    assert response.json()["backend_architect_run_id"] == pipeline["backend_architect_run"]["id"]
