from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_frontend_v3,
    setup_frontend_v3_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(
        client, email="fv3-schema@example.com", username="fv3schema"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv3-schema-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv3-schema-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v3_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v3(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for key in (
        "generated_files",
        "project_structure",
        "package_json",
        "environment_variables",
        "docker_configuration",
        "readme",
    ):
        assert key in artifact


async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(
        client, email="fv3-meta@example.com", username="fv3meta"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv3-meta-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv3-meta-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v3_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v3(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None
    assert data["artifact"]["model_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(
        client, email="fv3-history@example.com", username="fv3history"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv3-hist-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv3-hist-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v3_pipeline(client, tokens["access_token"], requirement["id"])
    await run_frontend_v3(client, tokens["access_token"], requirement["id"])
    await run_frontend_v3(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/frontend-v3/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.json()["total"] >= 2


async def test_completed_run_has_completed_at(client):
    _, tokens = await create_authenticated_user(
        client, email="fv3-complete@example.com", username="fv3complete"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv3-complete-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv3-complete-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v3_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v3(client, tokens["access_token"], requirement["id"])
    assert created.json()["completed_at"] is not None


async def test_generated_files_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="fv3-files@example.com", username="fv3files"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv3-files-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv3-files-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v3_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v3(client, tokens["access_token"], requirement["id"])
    files = created.json()["artifact"]["artifact_json"]["generated_files"]
    assert len(files) >= 50


async def test_package_json_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fv3-pkg@example.com", username="fv3pkg"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv3-pkg-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv3-pkg-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v3_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v3(client, tokens["access_token"], requirement["id"])
    package_json = created.json()["artifact"]["artifact_json"]["package_json"]
    assert package_json.get("name") == "generated-app"


async def test_docker_configuration_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fv3-docker@example.com", username="fv3docker"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv3-docker-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv3-docker-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v3_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v3(client, tokens["access_token"], requirement["id"])
    docker = created.json()["artifact"]["artifact_json"]["docker_configuration"]
    assert docker.get("base_image") == "node:20-alpine"


async def test_environment_variables_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fv3-env@example.com", username="fv3env"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv3-env-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv3-env-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v3_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v3(client, tokens["access_token"], requirement["id"])
    env_vars = created.json()["artifact"]["artifact_json"]["environment_variables"]
    assert len(env_vars) >= 1
    assert env_vars[0]["name"] == "NEXT_PUBLIC_API_URL"


async def test_readme_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fv3-readme@example.com", username="fv3readme"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv3-readme-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv3-readme-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v3_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v3(client, tokens["access_token"], requirement["id"])
    readme = created.json()["artifact"]["artifact_json"]["readme"]
    assert "Generated App" in readme


async def test_project_structure_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fv3-structure@example.com", username="fv3structure"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv3-struct-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv3-struct-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v3_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v3(client, tokens["access_token"], requirement["id"])
    structure = created.json()["artifact"]["artifact_json"]["project_structure"]
    assert structure.get("framework") == "nextjs-15"
