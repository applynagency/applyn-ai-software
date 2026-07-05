from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_docker_agents,
    setup_docker_agent_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(client, email="docker_agent-schema@example.com", username="integratsch")
    workspace = await create_workspace(client, tokens["access_token"], slug="docker_agent-schema-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="docker_agent-schema-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_docker_agent_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_docker_agents(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    assert "dockerfile_strategy" in artifact
    assert "docker_compose" in artifact
    assert "container_topology" in artifact
    assert "security_hardening" in artifact


async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(client, email="docker_agent-meta@example.com", username="integratmet")
    workspace = await create_workspace(client, tokens["access_token"], slug="docker_agent-meta-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="docker_agent-meta-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_docker_agent_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_docker_agents(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None
    assert data["artifact"]["model_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(client, email="docker_agent-history@example.com", username="integrathst")
    workspace = await create_workspace(client, tokens["access_token"], slug="docker_agent-hist-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="docker_agent-hist-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_docker_agent_pipeline(client, tokens["access_token"], requirement["id"])
    await run_docker_agents(client, tokens["access_token"], requirement["id"])
    await run_docker_agents(client, tokens["access_token"], requirement["id"])
    response = await client.get(f"/v1/agents/docker-agent/{requirement['id']}", headers=auth_headers(tokens["access_token"]))
    assert response.json()["total"] >= 2


async def test_required_sections_are_non_empty(client):
    _, tokens = await create_authenticated_user(client, email="docker_agent-mins@example.com", username="integratmin")
    workspace = await create_workspace(client, tokens["access_token"], slug="docker_agent-min-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="docker_agent-min-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_docker_agent_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_docker_agents(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for field in (
        "dockerfile_strategy",
        "docker_compose",
        "container_topology",
        "runtime_configuration",
        "image_optimization",
        "security_hardening",
    ):
        assert str(artifact[field]).strip()
