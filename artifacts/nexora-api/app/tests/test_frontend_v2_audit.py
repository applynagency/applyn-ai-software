from sqlalchemy import select

from app.models.audit import AuditLog
from app.tests.conftest import (
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_frontend_v2,
    setup_frontend_v2_pipeline,
)


async def test_frontend_v2_started_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="fv2-audit-start@example.com", username="fv2auditstart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-aud-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-aud-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "frontend_v2_started" in actions


async def test_frontend_v2_completed_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="fv2-audit-done@example.com", username="fv2auditdone"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-aud2-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-aud2-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "frontend_v2_completed" in actions
    assert "frontend_v2_validated" in actions


async def test_frontend_v2_validated_audit_has_score(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="fv2-audit-score@example.com", username="fv2auditscore"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv2-aud3-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv2-aud3-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v2_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v2(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == run_id,
                AuditLog.action == "frontend_v2_validated",
            )
        )
        log = result.scalars().first()
    assert log is not None
    assert "score" in (log.details or {})
