from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models.audit import AuditLog
from app.schemas.backend_execution import BackendExecutionOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    patch_backend_execution_agent,
    run_backend_execution,
    setup_backend_execution_pipeline,
)


async def test_backend_execution_started_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="fe-audit-start@example.com", username="feauditstart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-aud-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-aud-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "backend_execution_started" in actions


async def test_backend_execution_completed_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="fe-audit-done@example.com", username="feauditdone"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-aud2-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-aud2-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "backend_execution_completed" in actions


async def test_backend_execution_failed_audit(client):
    _, tokens = await create_authenticated_user(
        client, email="fe-audit-fail@example.com", username="feauditfail"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-aud-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-aud-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    invalid_output = BackendExecutionOutput(
        build_status="success",
        validation_status="passed",
        execution_logs=[],
        approval_status="BACKEND_APPROVED",
        startup_results={"status": "success"},
    )
    with patch_backend_execution_agent():
        with patch(
            "app.services.backend_execution.BackendExecutionAgent.run",
            new=AsyncMock(return_value=invalid_output),
        ):
            response = await client.post(
                "/v1/agents/backend-execution/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
    assert "validation" in response.json()["detail"].lower()


async def test_backend_execution_approved_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="fe-audit-approved@example.com", username="feauditapproved"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fe-aud-appr-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fe-aud-appr-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_execution_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_execution(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == run_id,
                AuditLog.action == "backend_execution_approved",
            )
        )
        log = result.scalars().first()
    assert log is not None
    assert log.details["approval_status"] == "BACKEND_APPROVED"
