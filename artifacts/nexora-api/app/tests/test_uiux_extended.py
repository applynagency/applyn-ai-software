from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_uiux_designer,
    setup_uiux_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-schema@example.com", username="uiuxschema"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="uiux-schema-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="uiux-schema-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_uiux_designer(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for key in (
        "information_architecture",
        "navigation_structure",
        "user_flows",
        "screen_inventory",
        "page_hierarchy",
        "role_screen_mapping",
        "design_system",
        "component_inventory",
        "frontend_handoff",
        "responsive_guidelines",
        "accessibility_guidelines",
    ):
        assert key in artifact


async def test_run_stores_model_metadata(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-meta@example.com", username="uiuxmeta"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="uiux-meta-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="uiux-meta-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_uiux_designer(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["model_used"] is not None
    assert data["tokens_used"] is not None
    assert data["artifact"]["model_used"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-history@example.com", username="uiuxhistory"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="uiux-hist-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="uiux-hist-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, tokens["access_token"], requirement["id"])
    await run_uiux_designer(client, tokens["access_token"], requirement["id"])
    await run_uiux_designer(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/uiux/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.json()["total"] >= 2


async def test_completed_run_has_completed_at(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-complete@example.com", username="uiuxcomplete"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="uiux-complete-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="uiux-complete-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_uiux_designer(client, tokens["access_token"], requirement["id"])
    assert created.json()["completed_at"] is not None


async def test_screen_inventory_meets_minimum(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-screens@example.com", username="uiuxscreens"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="uiux-screens-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="uiux-screens-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_uiux_designer(client, tokens["access_token"], requirement["id"])
    screens = created.json()["artifact"]["artifact_json"]["screen_inventory"]
    assert len(screens) >= 5
