from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_fullstack_assembly,
    setup_fullstack_assembly_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-schema@example.com", username="fsaschema"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-schema-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-schema-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for key in (
        "application_manifest",
        "frontend_package",
        "backend_package",
        "deployment_assets",
        "environment_variables",
        "docker_assets",
        "infrastructure_templates",
        "health_checks",
        "startup_configuration",
        "release_metadata",
        "readme",
        "assembly_status",
        "package_metadata",
    ):
        assert key in artifact


async def test_run_stores_assembler_metadata(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-meta@example.com", username="fsameta"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-meta-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-meta-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["assembler_version"] is not None
    assert data["artifact"]["assembler_version"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-history@example.com", username="fsahistory"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-hist-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-hist-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/fullstack-assembly/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.json()["total"] >= 2


async def test_completed_run_has_completed_at(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-complete@example.com", username="fsacomplete"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-complete-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-complete-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    assert created.json()["completed_at"] is not None


async def test_environment_variables_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-env@example.com", username="fsaenv"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-env-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-env-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    env_vars = created.json()["artifact"]["artifact_json"]["environment_variables"]
    assert len(env_vars) >= 1
    assert any(item.get("name") == "NEXT_PUBLIC_API_URL" for item in env_vars)


async def test_docker_assets_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-docker@example.com", username="fsadocker"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-docker-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-docker-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    docker = created.json()["artifact"]["artifact_json"]["docker_assets"]
    assert docker["compose_file"]["path"] == "docker-compose.yml"


async def test_assembly_status_stored_on_run(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-approval@example.com", username="fsaapproval"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-approval-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-approval-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    assert created.json()["assembly_status"] == "ASSEMBLY_APPROVED"


async def test_validation_score_on_run(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-score@example.com", username="fsascore"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-score-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-score-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    assert created.json()["validation_score"] >= 80


async def test_readme_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-readme@example.com", username="fsareadme"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-readme-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-readme-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    readme = created.json()["artifact"]["artifact_json"]["readme"]
    assert "Deployable Full-Stack Package" in readme


async def test_frontend_package_execution_summary_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-fe-pkg@example.com", username="fsafepkg"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-fe-pkg-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-fe-pkg-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    summary = created.json()["artifact"]["artifact_json"]["frontend_package"]["execution_summary"]
    assert summary["build_status"] == "success"
    assert summary["approval_status"] == "FRONTEND_APPROVED"
