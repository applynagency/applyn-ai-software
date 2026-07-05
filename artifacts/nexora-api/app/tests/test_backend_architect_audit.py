from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models.audit import AuditLog
from app.schemas.backend_architect import BackendArchitectOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    mock_backend_architect_output,
    patch_backend_architect_agent,
    run_backend_architect,
    setup_backend_architect_pipeline,
)


async def test_backend_architect_started_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="ba-arch-audit-start@example.com", username="baarchauditstart"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    created = await run_backend_architect(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "backend_architect_started" in actions


async def test_backend_architect_completed_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="ba-arch-audit-done@example.com", username="baarchauditdone"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    created = await run_backend_architect(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "backend_architect_completed" in actions
    assert "backend_architect_validated" in actions


async def test_backend_architect_validated_audit_has_score(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="ba-arch-audit-score@example.com", username="baarchauditscore"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    created = await run_backend_architect(
        client, tokens["access_token"], ctx["requirement"]["id"]
    )
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == run_id,
                AuditLog.action == "backend_architect_validated",
            )
        )
        log = result.scalars().first()
    assert log is not None
    assert "score" in (log.details or {})


async def test_backend_architect_failed_audit_on_validation_error(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="ba-arch-audit-fail@example.com", username="baarchauditfail"
    )
    ctx = await setup_backend_architect_pipeline(client, tokens["access_token"])
    invalid = mock_backend_architect_output()
    data = invalid.model_dump()
    data["api_architecture"] = data["api_architecture"][:1]
    invalid_output = BackendArchitectOutput(**data)
    with patch_backend_architect_agent():
        with patch(
            "app.services.backend_architect.BackendArchitectAgent.run",
            new=AsyncMock(return_value=(invalid_output, 50)),
        ):
            response = await client.post(
                "/v1/agents/backend-architect/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": ctx["requirement"]["id"]},
            )
    assert response.status_code == 422

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(AuditLog.action == "backend_architect_failed")
        )
        logs = list(result.scalars().all())
    assert any(
        (log.details or {}).get("error") not in (None, "", [])
        for log in logs
    )
