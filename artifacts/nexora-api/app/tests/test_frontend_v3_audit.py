from sqlalchemy import select

from app.models.audit import AuditLog
from app.tests.conftest import (
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_frontend_v3,
    setup_frontend_v3_pipeline,
)


async def test_frontend_v3_started_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="fv3-audit-start@example.com", username="fv3auditstart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv3-aud-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv3-aud-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v3_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v3(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "frontend_v3_started" in actions


async def test_frontend_v3_completed_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="fv3-audit-done@example.com", username="fv3auditdone"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv3-aud2-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv3-aud2-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v3_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v3(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "frontend_v3_completed" in actions
    assert "frontend_v3_validated" in actions


async def test_frontend_v3_validated_audit_has_score(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="fv3-audit-score@example.com", username="fv3auditscore"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fv3-aud3-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fv3-aud3-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_v3_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_v3(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == run_id,
                AuditLog.action == "frontend_v3_validated",
            )
        )
        log = result.scalars().first()
    assert log is not None
    assert "score" in (log.details or {})
