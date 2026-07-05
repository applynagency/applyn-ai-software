from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models.audit import AuditLog
from app.schemas.frontend_architect import FrontendArchitectOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    mock_frontend_architect_output,
    patch_frontend_architect_agent,
    run_frontend_architect,
    setup_frontend_architect_pipeline,
)


async def test_frontend_architect_started_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="fa-audit-start@example.com", username="faauditstart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-aud-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-aud-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "frontend_architect_started" in actions


async def test_frontend_architect_completed_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="fa-audit-done@example.com", username="faauditdone"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-aud2-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-aud2-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "frontend_architect_completed" in actions
    assert "frontend_architect_validated" in actions


async def test_frontend_architect_validated_audit_has_score(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="fa-audit-score@example.com", username="faauditscore"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-aud4-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-aud4-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_frontend_architect(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == run_id,
                AuditLog.action == "frontend_architect_validated",
            )
        )
        log = result.scalars().first()
    assert log is not None
    assert "score" in (log.details or {})


async def test_frontend_architect_validation_failure_returns_422(client):
    _, tokens = await create_authenticated_user(
        client, email="fa-audit-fail@example.com", username="faauditfail"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="fa-aud-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="fa-aud-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_frontend_architect_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_frontend_architect_output()
    data = invalid.model_dump()
    data["page_architecture"] = data["page_architecture"][:1]
    invalid_output = FrontendArchitectOutput(**data)
    with patch_frontend_architect_agent():
        with patch(
            "app.services.frontend_architect.FrontendArchitectAgent.run",
            new=AsyncMock(return_value=(invalid_output, 50)),
        ):
            response = await client.post(
                "/v1/agents/frontend-architect/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
    assert "validation" in response.json()["detail"].lower()
