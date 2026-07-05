from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_product_owner_run,
    create_project,
    create_requirement,
    create_workspace,
    run_business_analyst,
)


async def test_run_business_analyst_success(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-run@example.com", username="barun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    response = await run_business_analyst(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_product_owner_first(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-no-po@example.com", username="banopo"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-no-po-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-no-po-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    response = await run_business_analyst(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_business_analyst_run(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-get-run@example.com", username="bagetrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-get-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-get-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    created = await run_business_analyst(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(
        f"/v1/agents/business-analyst/runs/{run_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_business_analyst_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-get-art@example.com", username="bagetart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-art-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-art-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    created = await run_business_analyst(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/business-analyst/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["artifact_json"]["functional_requirements"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-list@example.com", username="balist"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-list-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-list-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    await run_business_analyst(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/business-analyst/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_artifact_has_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-md@example.com", username="bamd"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-md-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-md-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    created = await run_business_analyst(client, tokens["access_token"], requirement["id"])
    assert "Business Analysis Document" in created.json()["artifact"]["artifact_markdown"]


async def test_run_stores_prompt_version(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-prompt@example.com", username="baprompt"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-pv-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-pv-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    created = await run_business_analyst(client, tokens["access_token"], requirement["id"])
    assert created.json()["prompt_version"] == "1.0.0"


async def test_run_stores_product_owner_run_id(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-po-link@example.com", username="bapolink"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    po_run = await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    created = await run_business_analyst(client, tokens["access_token"], requirement["id"])
    assert created.json()["product_owner_run_id"] == po_run["id"]


async def test_run_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-notfound@example.com", username="banotfound"
    )
    response = await client.get(
        "/v1/agents/business-analyst/runs/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404


async def test_artifact_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-art-missing@example.com", username="baartmissing"
    )
    response = await client.get(
        "/v1/agents/business-analyst/artifacts/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404
