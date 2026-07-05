from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_fullstack_assembly,
    setup_fullstack_assembly_pipeline,
)


async def test_post_run_returns_201(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-api-post@example.com", username="fsaapipost"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201


async def test_get_runs_endpoint_returns_list(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-api-list@example.com", username="fsaapilist"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-list-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-list-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/fullstack-assembly/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert "items" in response.json()
    assert "total" in response.json()


async def test_artifact_endpoint_returns_json_and_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-api-art@example.com", username="fsaapiart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-art-api-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-art-api-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/fullstack-assembly/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    body = response.json()
    assert response.status_code == 200
    assert body["artifact_json"]
    assert body["artifact_markdown"]
    assert body["assembly_status"] is not None


async def test_success_response_includes_validation_score(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-api-score@example.com", username="fsaapiscore"
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
    data = created.json()
    assert data["validation_score"] is not None
    assert data["validation_score"] >= 80
    assert data["artifact"]["validation_score"] == data["validation_score"]


async def test_success_response_includes_assembly_status(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-api-status@example.com", username="fsaapistatus"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-status-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-status-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["assembly_status"] in (
        "ASSEMBLY_APPROVED",
        "ASSEMBLY_APPROVED_WITH_WARNINGS",
        "ASSEMBLY_NEEDS_REVIEW",
    )
    assert data["artifact"]["assembly_status"] == data["assembly_status"]
