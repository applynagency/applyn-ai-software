from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_fullstack_assembly,
    setup_fullstack_assembly_pipeline,
)


async def test_run_fullstack_assembly_success(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-run@example.com", username="fsarun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    response = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["assembly_status"] == "ASSEMBLY_APPROVED"
    assert data["validation_score"] is not None
    assert data["artifact"] is not None


async def test_run_requires_frontend_execution_first(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-no-fe@example.com", username="fsanofe"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-no-fe-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-no-fe-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    response = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_get_fullstack_assembly_run(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-get-run@example.com", username="fsagetrun"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-get-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-get-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    response = await client.get(
        f"/v1/agents/fullstack-assembly/runs/{run_id}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == run_id


async def test_get_fullstack_assembly_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-get-art@example.com", username="fsagetart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-art-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-art-proj"
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
    assert response.status_code == 200
    assert response.json()["artifact_json"]["application_manifest"]


async def test_list_runs_by_requirement(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-list@example.com", username="fsalist"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-list-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-list-proj"
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
    assert response.json()["total"] >= 1


async def test_artifact_has_markdown(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-md@example.com", username="fsamd"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-md-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-md-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    assert "Full Stack Assembly Package" in created.json()["artifact"]["artifact_markdown"]


async def test_run_stores_assembler_version(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-ver@example.com", username="fsaver"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-ver-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-ver-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_fullstack_assembly_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    assert created.json()["assembler_version"] == "2.0.0"


async def test_run_stores_frontend_execution_run_id(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-link@example.com", username="fsalink"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_fullstack_assembly_pipeline(
        client, tokens["access_token"], requirement["id"]
    )
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    assert created.json()["frontend_execution_run_id"] == pipeline["frontend_execution_run"]["id"]


async def test_run_requires_backend_execution_first(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-no-be@example.com", username="fsanobe"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-no-be-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-no-be-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    from app.tests.conftest import run_frontend_execution, setup_frontend_execution_pipeline

    await setup_frontend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    await run_frontend_execution(client, tokens["access_token"], requirement["id"])
    response = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    assert response.status_code == 422


async def test_run_links_backend_execution_run_id(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-be-link@example.com", username="fsabelink"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fsa-be-link-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fsa-be-link-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    pipeline = await setup_fullstack_assembly_pipeline(
        client, tokens["access_token"], requirement["id"]
    )
    created = await run_fullstack_assembly(client, tokens["access_token"], requirement["id"])
    assert created.json()["backend_execution_run_id"] == pipeline["backend_execution_run"]["id"]
    backend = created.json()["artifact"]["artifact_json"]["backend_package"]
    assert backend["included"] is True


async def test_run_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-notfound@example.com", username="fsanotfound"
    )
    response = await client.get(
        "/v1/agents/fullstack-assembly/runs/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404


async def test_artifact_not_found(client):
    _, tokens = await create_authenticated_user(
        client, email="fsa-art-missing@example.com", username="fsaartmissing"
    )
    response = await client.get(
        "/v1/agents/fullstack-assembly/artifacts/missing-id",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 404
