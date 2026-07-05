from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_frontend_architect,
    setup_frontend_architect_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-schema@example.com", username="faschema"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-schema-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-schema-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for key in (
        "frontend_stack",
        "routing_architecture",
        "page_architecture",
        "layout_architecture",
        "component_architecture",
        "state_management",
        "api_integration",
        "authentication",
        "forms",
        "design_system_mapping",
        "folder_structure",
        "deployment_architecture",
        "development_guidelines",
    ):
        assert key in artifact


async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-meta@example.com", username="fameta"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-meta-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-meta-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None
    assert data["artifact"]["model_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-history@example.com", username="fahistory"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-hist-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-hist-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/frontend-architect/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.json()["total"] >= 2


async def test_completed_run_has_completed_at(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-complete@example.com", username="facomplete"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-complete-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-complete-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    assert created.json()["completed_at"] is not None


async def test_page_architecture_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-pages@example.com", username="fapages"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-pages-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-pages-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    pages = created.json()["artifact"]["artifact_json"]["page_architecture"]
    assert len(pages) >= 10


async def test_component_architecture_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-components@example.com", username="facomponents"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-comp-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-comp-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    components = created.json()["artifact"]["artifact_json"]["component_architecture"]
    assert len(components) >= 20


async def test_forms_meet_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-forms@example.com", username="faforms"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-forms-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-forms-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    forms = created.json()["artifact"]["artifact_json"]["forms"]
    assert len(forms) >= 5


async def test_routing_architecture_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-routes@example.com", username="faroutes"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-routes-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-routes-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    routes = created.json()["artifact"]["artifact_json"]["routing_architecture"]
    assert len(routes) >= 10


async def test_api_integrations_meet_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-api@example.com", username="faapi"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    integrations = created.json()["artifact"]["artifact_json"]["api_integration"]["integrations"]
    assert len(integrations) >= 5
