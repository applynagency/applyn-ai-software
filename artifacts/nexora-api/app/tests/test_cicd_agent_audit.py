from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.tests.conftest import (
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_cicd_agent,
    setup_cicd_agent_pipeline,
)


async def test_cicd_agent_started_audit(client):
    _, tokens = await create_authenticated_user(client, email="cicd_agent-audit@example.com", username="cicd_ageaudit")
    workspace = await create_workspace(client, tokens["access_token"], slug="cicd_agent-aud-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="cicd_agent-aud-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_cicd_agent_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_cicd_agent(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "cicd_started" in actions


async def test_cicd_agent_completed_audit(client):
    _, tokens = await create_authenticated_user(client, email="cicd_agent-aud-done@example.com", username="cicd_ageauddn")
    workspace = await create_workspace(client, tokens["access_token"], slug="cicd_agent-aud-done-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="cicd_agent-aud-done-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_cicd_agent_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_cicd_agent(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "cicd_completed" in actions


async def test_cicd_agent_validated_audit(client):
    _, tokens = await create_authenticated_user(client, email="cicd_agent-aud-val@example.com", username="cicd_ageaudvl")
    workspace = await create_workspace(client, tokens["access_token"], slug="cicd_agent-aud-val-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="cicd_agent-aud-val-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_cicd_agent_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_cicd_agent(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "cicd_validated" in actions
