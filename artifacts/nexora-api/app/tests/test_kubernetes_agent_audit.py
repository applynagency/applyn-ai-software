from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.tests.conftest import (
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    run_kubernetes_agent,
    setup_kubernetes_pipeline,
)


async def _run(client, email, username, slug):
    _, tokens = await create_authenticated_user(client, email=email, username=username)
    workspace = await create_workspace(client, tokens["access_token"], slug=f"{slug}-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug=f"{slug}-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_kubernetes_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_kubernetes_agent(client, tokens["access_token"], requirement["id"])
    return created.json()["id"]


async def _actions_for(run_id):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        return {log.action for log in result.scalars().all()}


async def test_kubernetes_started_audit(client):
    run_id = await _run(client, "k8s-audit@example.com", "k8saudit", "k8s-aud")
    actions = await _actions_for(run_id)
    assert "kubernetes_started" in actions


async def test_kubernetes_completed_audit(client):
    run_id = await _run(client, "k8s-aud-done@example.com", "k8sauddn", "k8s-aud-done")
    actions = await _actions_for(run_id)
    assert "kubernetes_completed" in actions


async def test_kubernetes_validated_audit(client):
    run_id = await _run(client, "k8s-aud-val@example.com", "k8saudvl", "k8s-aud-val")
    actions = await _actions_for(run_id)
    assert "kubernetes_validated" in actions
