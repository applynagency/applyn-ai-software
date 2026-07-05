from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_uiux_designer,
    setup_uiux_pipeline,
)


async def test_run_uiux_designer_success(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-run@example.com", username="uiuxrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="uiux-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="uiux-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_uiux_designer(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_business_analyst_first(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-no-ba@example.com", username="uiuxnoba"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="uiux-no-ba-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="uiux-no-ba-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    response = await run_uiux_designer(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_uiux_run(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-get-run@example.com", username="uiuxgetrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="uiux-get-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="uiux-get-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_uiux_designer(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(
        f"/v1/agents/uiux/runs/{run_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_uiux_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-get-art@example.com", username="uiuxgetart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="uiux-art-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="uiux-art-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_uiux_designer(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/uiux/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["artifact_json"]["screen_inventory"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-list@example.com", username="uiuxlist"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="uiux-list-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="uiux-list-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, tokens["access_token"], requirement["id"])
    await run_uiux_designer(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/uiux/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_artifact_has_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-md@example.com", username="uiuxmd"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="uiux-md-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="uiux-md-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_uiux_designer(client, tokens["access_token"], requirement["id"])
    assert "UI/UX Design Specification" in created.json()["artifact"]["artifact_markdown"]


async def test_run_stores_prompt_version(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-prompt@example.com", username="uiuxprompt"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="uiux-pv-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="uiux-pv-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_uiux_designer(client, tokens["access_token"], requirement["id"])
    assert created.json()["prompt_version"] == "1.0.0"


async def test_run_stores_business_analyst_run_id(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-ba-link@example.com", username="uiuxbalink"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="uiux-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="uiux-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_uiux_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_uiux_designer(client, tokens["access_token"], requirement["id"])
    assert created.json()["business_analyst_run_id"] == pipeline["business_analyst_run"]["id"]


async def test_run_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-notfound@example.com", username="uiuxnotfound"
    )
    response = await client.get(
        "/v1/agents/uiux/runs/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404


async def test_artifact_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="uiux-art-missing@example.com", username="uiuxartmissing"
    )
    response = await client.get(
        "/v1/agents/uiux/artifacts/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404
