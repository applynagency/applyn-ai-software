from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models.audit import AuditLog
from app.schemas.security_test import SecurityTestOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    mock_security_test_output,
    patch_security_test_agent,
    run_security_tests,
    setup_security_test_pipeline,
)


async def test_security_test_started_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(client, email="security_test-audit-start@example.com", username="securityast")
    workspace = await create_workspace(client, tokens["access_token"], slug="security_test-aud-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="security_test-aud-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_security_test_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_security_tests(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "security_test_started" in actions


async def test_security_test_completed_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(client, email="security_test-audit-done@example.com", username="securityadn")
    workspace = await create_workspace(client, tokens["access_token"], slug="security_test-aud2-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="security_test-aud2-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_security_test_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_security_tests(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "security_test_completed" in actions
    assert "security_test_validated" in actions



async def test_security_test_validation_failure_returns_422(client):
    _, tokens = await create_authenticated_user(client, email="security_test-audit-fail@example.com", username="securityafl")
    workspace = await create_workspace(client, tokens["access_token"], slug="security_test-aud-fail-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="security_test-aud-fail-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_security_test_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_security_test_output()
    data = invalid.model_dump(mode="json")
    data["owasp_assessment"] = data["owasp_assessment"][:1]
    invalid_output = SecurityTestOutput(**data)
    with patch_security_test_agent():
        with patch("app.services.security_test.SecurityTestAgent.run", new=AsyncMock(return_value=(invalid_output, 50))):
            response = await client.post(
                "/v1/agents/security-tests/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
