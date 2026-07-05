from sqlalchemy import select

from app.models.audit import AuditLog
from app.tests.conftest import (
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_uiux_designer,
    setup_uiux_pipeline,
)


async def test_uiux_started_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="uiux-audit-start@example.com", username="uiuxauditstart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="uiux-aud-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="uiux-aud-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_uiux_designer(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "uiux_started" in actions


async def test_uiux_completed_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="uiux-audit-done@example.com", username="uiuxauditdone"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="uiux-aud2-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="uiux-aud2-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_uiux_designer(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "uiux_completed" in actions
    assert "uiux_validated" in actions


async def test_uiux_validated_audit_has_score(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="uiux-audit-score@example.com", username="uiuxauditscore"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="uiux-aud4-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="uiux-aud4-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_uiux_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_uiux_designer(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == run_id,
                AuditLog.action == "uiux_validated",
            )
        )
        log = result.scalars().first()
    assert log is not None
    assert "score" in (log.details or {})
