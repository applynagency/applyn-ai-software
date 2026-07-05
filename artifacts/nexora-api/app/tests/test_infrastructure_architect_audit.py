from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.tests.conftest import (
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_infrastructure_architect,
    setup_infrastructure_architect_pipeline,
)


async def test_infrastructure_architect_started_audit(client):
    _, tokens = await create_authenticated_user(client, email="infrastructure_architect-audit@example.com", username="infrastraudit")
    workspace = await create_workspace(client, tokens["access_token"], slug="infrastructure_architect-aud-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="infrastructure_architect-aud-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_infrastructure_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_infrastructure_architect(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "infrastructure_architect_started" in actions


async def test_infrastructure_architect_completed_audit(client):
    _, tokens = await create_authenticated_user(client, email="infrastructure_architect-aud-done@example.com", username="infrastrauddn")
    workspace = await create_workspace(client, tokens["access_token"], slug="infrastructure_architect-aud-done-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="infrastructure_architect-aud-done-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_infrastructure_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_infrastructure_architect(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "infrastructure_architect_completed" in actions


async def test_infrastructure_architect_validated_audit(client):
    _, tokens = await create_authenticated_user(client, email="infrastructure_architect-aud-val@example.com", username="infrastraudvl")
    workspace = await create_workspace(client, tokens["access_token"], slug="infrastructure_architect-aud-val-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="infrastructure_architect-aud-val-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_infrastructure_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_infrastructure_architect(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "infrastructure_architect_validated" in actions
