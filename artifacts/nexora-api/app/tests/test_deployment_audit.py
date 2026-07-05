from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models.audit import AuditLog
from app.schemas.deployment import DeploymentOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    patch_deployment_agent,
    run_deployment,
    setup_deployment_pipeline,
)


async def test_deployment_started_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="dep-audit-start@example.com", username="depauditstart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-aud-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-aud-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "deployment_started" in actions


async def test_deployment_completed_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="dep-audit-done@example.com", username="depauditdone"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-aud2-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-aud2-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "deployment_completed" in actions


async def test_deployment_failed_audit_on_validation(client):
    _, tokens = await create_authenticated_user(
        client, email="dep-audit-fail@example.com", username="depauditfail"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-aud-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-aud-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    invalid_output = DeploymentOutput.model_construct(
        deployment_provider="AZURE",
        deployment_status="DEPLOYED",
        live_url="",
        deployment_logs=[],
    )
    with patch_deployment_agent():
        with patch(
            "app.services.deployment.DeploymentAgent.run",
            new=AsyncMock(return_value=invalid_output),
        ):
            response = await client.post(
                "/v1/agents/deployment/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
    assert "validation" in response.json()["detail"].lower()


async def test_deployment_rollback_started_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="dep-audit-rb-start@example.com", username="depauditrbstart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-aud-rb-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-aud-rb-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    deployment_id = created.json()["id"]
    await client.post(
        f"/v1/deployments/{deployment_id}/rollback",
        headers=auth_headers(tokens["access_token"]),
    )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == deployment_id,
                AuditLog.action == "deployment_rollback_started",
            )
        )
        log = result.scalars().first()
    assert log is not None


async def test_deployment_rollback_completed_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="dep-audit-rb-done@example.com", username="depauditrbdone"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="dep-aud-rb2-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="dep-aud-rb2-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_deployment_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_deployment(client, tokens["access_token"], requirement["id"])
    deployment_id = created.json()["id"]
    await client.post(
        f"/v1/deployments/{deployment_id}/rollback",
        headers=auth_headers(tokens["access_token"]),
    )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == deployment_id,
                AuditLog.action == "deployment_rollback_completed",
            )
        )
        log = result.scalars().first()
    assert log is not None
    assert "live_url" in (log.details or {})
