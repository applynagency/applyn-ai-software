from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.tests.conftest import (
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_docker_agent,
    setup_docker_agent_pipeline,
)


async def test_docker_agent_started_audit(client):
    _, tokens = await create_authenticated_user(client, email="docker_agent-audit@example.com", username="docker_aaudit")
    workspace = await create_workspace(client, tokens["access_token"], slug="docker_agent-aud-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="docker_agent-aud-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_docker_agent_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_docker_agent(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "docker_agent_started" in actions


async def test_docker_agent_completed_audit(client):
    _, tokens = await create_authenticated_user(client, email="docker_agent-aud-done@example.com", username="docker_aauddn")
    workspace = await create_workspace(client, tokens["access_token"], slug="docker_agent-aud-done-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="docker_agent-aud-done-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_docker_agent_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_docker_agent(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "docker_agent_completed" in actions


async def test_docker_agent_validated_audit(client):
    _, tokens = await create_authenticated_user(client, email="docker_agent-aud-val@example.com", username="docker_aaudvl")
    workspace = await create_workspace(client, tokens["access_token"], slug="docker_agent-aud-val-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="docker_agent-aud-val-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_docker_agent_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_docker_agent(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "docker_agent_validated" in actions
