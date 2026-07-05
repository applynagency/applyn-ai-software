from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_frontend_v2,
    setup_frontend_v2_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-schema@example.com", username="fv2schema"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-schema-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-schema-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for key in (
        "file_structure",
        "page_files",
        "component_files",
        "layout_files",
        "service_files",
        "store_files",
        "hook_files",
        "provider_files",
        "type_files",
        "middleware_files",
        "utility_files",
        "form_files",
        "validation_files",
    ):
        assert key in artifact


async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-meta@example.com", username="fv2meta"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-meta-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-meta-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None
    assert data["artifact"]["model_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-history@example.com", username="fv2history"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-hist-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-hist-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/frontend-v2/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.json()["total"] >= 2


async def test_completed_run_has_completed_at(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-complete@example.com", username="fv2complete"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-complete-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-complete-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    assert created.json()["completed_at"] is not None


async def test_page_files_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-pages@example.com", username="fv2pages"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-pages-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-pages-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    pages = created.json()["artifact"]["artifact_json"]["page_files"]
    assert len(pages) >= 10


async def test_component_files_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-components@example.com", username="fv2components"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-cmp-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-cmp-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    components = created.json()["artifact"]["artifact_json"]["component_files"]
    assert len(components) >= 20


async def test_store_files_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-store@example.com", username="fv2store"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-store-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-store-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    stores = created.json()["artifact"]["artifact_json"]["store_files"]
    assert len(stores) >= 5


async def test_service_files_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-services@example.com", username="fv2services"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-svc-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-svc-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    services = created.json()["artifact"]["artifact_json"]["service_files"]
    assert len(services) >= 5


async def test_hook_files_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="fv2-hooks@example.com", username="fv2hooks"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-hooks-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-hooks-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    hooks = created.json()["artifact"]["artifact_json"]["hook_files"]
    assert len(hooks) >= 5
