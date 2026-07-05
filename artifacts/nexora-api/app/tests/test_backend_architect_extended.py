from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    run_backend_architect,
    setup_backend_architect_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-schema@example.com", username="baarchschema"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    created = await run_backend_architect(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    artifact = created.json()["artifact"]["artifact_json"]
    for key in (
        "backend_stack",
        "service_architecture",
        "api_architecture",
        "database_architecture",
        "authentication_architecture",
        "authorization_architecture",
        "integration_architecture",
        "caching_architecture",
        "event_architecture",
        "deployment_architecture",
        "folder_structure",
        "security_architecture",
        "development_guidelines",
    ):
        assert key in artifact


async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-meta@example.com", username="baarchmeta"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    created = await run_backend_architect(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None
    assert data["artifact"]["model_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-history@example.com", username="baarchhistory"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    await run_backend_architect(client, tokens["access_token"], ctx["requirement"]["id"])
    await run_backend_architect(client, tokens["access_token"], ctx["requirement"]["id"])
    response = await client.get(
        f"/v1/agents/backend-architect/{ctx['requirement']['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.json()["total"] >= 2


async def test_completed_run_has_completed_at(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-complete@example.com", username="baarchcomplete"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    created = await run_backend_architect(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    assert created.json()["completed_at"] is not None


async def test_api_architecture_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-api@example.com", username="baarchapi"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    created = await run_backend_architect(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    apis = created.json()["artifact"]["artifact_json"]["api_architecture"]
    assert len(apis) >= 10


async def test_database_architecture_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-db@example.com", username="baarchdb"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    created = await run_backend_architect(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    entities = created.json()["artifact"]["artifact_json"]["database_architecture"]
    assert len(entities) >= 10


async def test_integration_architecture_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-int@example.com", username="baarchint"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    created = await run_backend_architect(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    integrations = created.json()["artifact"]["artifact_json"]["integration_architecture"]
    assert len(integrations) >= 3


async def test_security_controls_meet_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-sec@example.com", username="baarchsec"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    created = await run_backend_architect(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    controls = created.json()["artifact"]["artifact_json"]["security_architecture"]["controls"]
    assert len(controls) >= 3


async def test_user_roles_meet_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-roles@example.com", username="baarchroles"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    created = await run_backend_architect(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    roles = created.json()["artifact"]["artifact_json"]["authorization_architecture"]["roles"]
    assert len(roles) >= 3


async def test_backend_stack_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-stack@example.com", username="baarchstack"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    created = await run_backend_architect(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    stack = created.json()["artifact"]["artifact_json"]["backend_stack"]
    assert stack.get("language")
    assert stack.get("framework")
