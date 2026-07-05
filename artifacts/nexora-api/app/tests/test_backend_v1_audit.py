from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models.audit import AuditLog
from app.schemas.backend_v1 import BackendDeveloperV1Output
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    mock_backend_v1_output,
    patch_backend_v1_agent,
    run_backend_v1,
    setup_backend_v1_pipeline,
)


async def test_backend_v1_started_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="bv1-audit-start@example.com", username="bv1auditstart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-aud-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-aud-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v1(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "backend_v1_started" in actions


async def test_backend_v1_completed_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="bv1-audit-done@example.com", username="bv1auditdone"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-aud2-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-aud2-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v1(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "backend_v1_completed" in actions
    assert "backend_v1_validated" in actions


async def test_backend_v1_validated_audit_has_score(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="bv1-audit-score@example.com", username="bv1auditscore"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-aud3-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-aud3-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_backend_v1(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == run_id,
                AuditLog.action == "backend_v1_validated",
            )
        )
        log = result.scalars().first()
    assert log is not None
    assert "score" in (log.details or {})


async def test_backend_v1_failed_audit_on_validation_error(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="bv1-audit-fail@example.com", username="bv1auditfail"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="bv1-aud-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="bv1-aud-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_backend_v1_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_backend_v1_output()
    data = invalid.model_dump()
    data["service_specifications"] = data["service_specifications"][:1]
    invalid_output = BackendDeveloperV1Output(**data)
    with patch_backend_v1_agent():
        with patch(
            "app.services.backend_v1.BackendDeveloperV1Agent.run",
            new=AsyncMock(return_value=(invalid_output, 50)),
        ):
            response = await client.post(
                "/v1/agents/backend-v1/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "backend_v1_failed",
                AuditLog.resource_type == "backend_v1_run",
            )
        )
        logs = result.scalars().all()
    assert len(logs) >= 1
