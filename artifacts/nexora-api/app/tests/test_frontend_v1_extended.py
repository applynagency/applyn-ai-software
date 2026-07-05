from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_frontend_v1,
    setup_frontend_v1_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-schema@example.com", username="fv1schema"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-schema-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-schema-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for key in (
        "project_structure",
        "route_structure",
        "layout_structure",
        "page_structure",
        "component_structure",
        "api_client_structure",
        "state_management",
        "form_architecture",
        "validation_strategy",
        "folder_organization",
        "development_conventions",
        "module_breakdown",
    ):
        assert key in artifact


async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-meta@example.com", username="fv1meta"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-meta-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-meta-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None
    assert data["artifact"]["model_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-history@example.com", username="fv1history"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-hist-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-hist-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/frontend-v1/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.json()["total"] >= 2


async def test_completed_run_has_completed_at(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-complete@example.com", username="fv1complete"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-complete-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-complete-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    assert created.json()["completed_at"] is not None


async def test_page_structure_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-pages@example.com", username="fv1pages"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-pages-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-pages-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    pages = created.json()["artifact"]["artifact_json"]["page_structure"]
    assert len(pages) >= 10


async def test_component_structure_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-components@example.com", username="fv1components"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-cmp-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-cmp-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    components = created.json()["artifact"]["artifact_json"]["component_structure"]
    assert len(components) >= 20


async def test_state_modules_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-state@example.com", username="fv1state"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-state-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-state-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    modules = created.json()["artifact"]["artifact_json"]["state_management"]["modules"]
    assert len(modules) >= 5


async def test_route_structure_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-routes@example.com", username="fv1routes"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-routes-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-routes-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    routes = created.json()["artifact"]["artifact_json"]["route_structure"]
    assert len(routes) >= 10


async def test_form_architecture_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="fv1-forms@example.com", username="fv1forms"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv1-forms-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv1-forms-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v1(client, tokens["access_token"], requirement["id"])
    forms = created.json()["artifact"]["artifact_json"]["form_architecture"]
    assert len(forms) >= 5
