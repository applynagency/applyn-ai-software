from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_backend_architect,
    setup_backend_architect_pipeline,
)


async def test_run_backend_architect_success(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-run@example.com", username="baarchrun"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    response = await run_backend_architect(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_business_analyst_first(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-no-ba@example.com", username="baarchnoba"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-arch-no-ba-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-arch-no-ba-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    response = await run_backend_architect(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_backend_architect_run(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-get-run@example.com", username="baarchgetrun"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    created = await run_backend_architect(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    run_id = created.json()["id"]
    response = await client.get(
        f"/v1/agents/backend-architect/runs/{run_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_backend_architect_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-get-art@example.com", username="baarchgetart"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    created = await run_backend_architect(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    artifact_id = created.json()["artifact"]["id"]
    response = await client.get(
        f"/v1/agents/backend-architect/artifacts/{artifact_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["artifact_json"]["api_architecture"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-list@example.com", username="baarchlist"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    await run_backend_architect(client, tokens["access_token"], ctx["requirement"]["id"])
    response = await client.get(
        f"/v1/agents/backend-architect/{ctx['requirement']['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_artifact_has_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-md@example.com", username="baarchmd"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    created = await run_backend_architect(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    assert "Backend Architecture Blueprint" in created.json()["artifact"]["artifact_markdown"]


async def test_run_stores_prompt_version(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-prompt@example.com", username="baarchprompt"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    created = await run_backend_architect(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    assert created.json()["prompt_version"] == "1.0.0"


async def test_run_stores_business_analyst_run_id(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-ba-link@example.com", username="baarchbalink"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    created = await run_backend_architect(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    assert created.json()["business_analyst_run_id"] == ctx["business_analyst_run"]["id"]


async def test_run_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-notfound@example.com", username="baarchnotfound"
    )
    response = await client.get(
        "/v1/agents/backend-architect/runs/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404


async def test_artifact_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="ba-arch-art-missing@example.com", username="baarchartmissing"
    )
    response = await client.get(
        "/v1/agents/backend-architect/artifacts/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404
