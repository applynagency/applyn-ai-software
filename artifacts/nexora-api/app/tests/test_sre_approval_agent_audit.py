from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.tests.conftest import (
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_sre_approval,
    setup_sre_approval_pipeline,
)


async def _run(client, email, username, slug):
    _, tokens = await create_authenticated_user(client, email=email, username=username)
    workspace = await create_workspace(client, tokens["access_token"], slug=f"{slug}-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug=f"{slug}-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_sre_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_sre_approval(client, tokens["access_token"], requirement["id"])
    return created.json()["id"]


async def _actions_for(run_id):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        return {log.action for log in result.scalars().all()}


async def test_sre_approval_started_audit(client):
    run_id = await _run(client, "sre-audit@example.com", "sreaudit", "sre-aud")
    actions = await _actions_for(run_id)
    assert "sre_approval_started" in actions


async def test_sre_approval_completed_audit(client):
    run_id = await _run(client, "sre-aud-done@example.com", "sreauddn", "sre-aud-done")
    actions = await _actions_for(run_id)
    assert "sre_approval_completed" in actions


async def test_sre_approved_decision_audit(client):
    run_id = await _run(client, "sre-aud-dec@example.com", "sreauddec", "sre-aud-dec")
    actions = await _actions_for(run_id)
    assert "sre_approved" in actions
