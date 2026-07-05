from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_backend_execution,
    setup_backend_execution_pipeline,
)


async def test_artifact_contains_all_schema_sections(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-schema@example.com", username="feschema"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-schema-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-schema-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    for key in (
        "build_status",
        "validation_status",
        "approval_status",
        "execution_logs",
        "ruff_results",
        "mypy_results",
        "pytest_results",
        "startup_results",
        "dependency_results",
        "migration_results",
        "environment_results",
    ):
        assert key in artifact


async def test_run_stores_executor_metadata(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-meta@example.com", username="femeta"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-meta-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-meta-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    data = created.json()
    assert data["executor_version"] is not None
    assert data["artifact"]["executor_version"] is not None


async def test_multiple_runs_create_history(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-history@example.com", username="fehistory"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-hist-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-hist-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    await run_backend_execution(client, tokens["access_token"], requirement["id"])
    await run_backend_execution(client, tokens["access_token"], requirement["id"])
    response = await client.get(
        f"/v1/agents/backend-execution/{requirement['id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.json()["total"] >= 2


async def test_completed_run_has_completed_at(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-complete@example.com", username="fecomplete"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-complete-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-complete-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    assert created.json()["completed_at"] is not None


async def test_execution_logs_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-logs@example.com", username="felogs"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-logs-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-logs-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    logs = created.json()["artifact"]["artifact_json"]["execution_logs"]
    assert len(logs) >= 1
    assert any("pip install" in log for log in logs)


async def test_step_results_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-steps@example.com", username="festeps"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-steps-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-steps-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    artifact = created.json()["artifact"]["artifact_json"]
    assert artifact["ruff_results"]["status"] == "success"
    assert artifact["startup_results"]["status"] == "success"


async def test_approval_status_stored_on_run(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-approval@example.com", username="feapproval"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-approval-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-approval-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    assert created.json()["approval_status"] == "BACKEND_APPROVED"


async def test_build_status_on_run(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-build@example.com", username="febuild"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-build-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-build-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    assert created.json()["build_status"] == "success"


async def test_validation_status_on_run(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-validation@example.com", username="fevalidation"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-val-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-val-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    assert created.json()["validation_status"] == "passed"


async def test_dependency_results_present_in_artifact(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-install@example.com", username="feinstall"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-install-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-install-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    install = created.json()["artifact"]["artifact_json"]["dependency_results"]
    assert install["command"] == "pip check"
    assert install["exit_code"] == 0
