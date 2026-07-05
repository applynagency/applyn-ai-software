from sqlalchemy import select

from app.models.audit import AuditLog
from app.tests.conftest import (
    create_authenticated_user,
    create_product_owner_run,
    create_project,
    create_requirement,
    create_workspace,
    run_business_analyst,
)


async def _audit_actions(session, run_id):
    result = await session.execute(select(AuditLog))
    logs = list(result.scalars().all())
    return {
        log.action
        for log in logs
        if log.resource_id == run_id
        or (log.details or {}).get("run_id") == run_id
        or log.resource_id == run_id
    }


async def test_business_analyst_started_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="ba-audit-start@example.com", username="baauditstart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-aud-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-aud-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    created = await run_business_analyst(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(AuditLog.resource_id == run_id)
        )
        actions = {log.action for log in result.scalars().all()}
    assert "business_analyst_started" in actions


async def test_business_analyst_completed_audit(client):
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="ba-audit-done@example.com", username="baauditdone"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-aud2-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-aud2-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    created = await run_business_analyst(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(AuditLog.resource_id == run_id)
        )
        actions = {log.action for log in result.scalars().all()}
    assert "business_analyst_completed" in actions
    assert "business_analyst_validated" in actions


async def test_business_analyst_validated_audit_has_score(client):
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="ba-audit-score@example.com", username="baauditscore"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ba-aud3-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ba-aud3-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await create_product_owner_run(client, tokens["access_token"], requirement["id"])
    created = await run_business_analyst(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == run_id,
                AuditLog.action == "business_analyst_validated",
            )
        )
        log = result.scalars().first()
    assert log is not None
    assert "score" in (log.details or {})
