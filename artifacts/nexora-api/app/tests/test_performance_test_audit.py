from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models.audit import AuditLog
from app.schemas.performance_test import PerformanceTestOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    mock_performance_test_output,
    patch_performance_test_agent,
    run_performance_tests,
    setup_performance_test_pipeline,
)


async def test_performance_test_started_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(client, email="performance_test-audit-start@example.com", username="performaast")
    workspace = await create_workspace(client, tokens["access_token"], slug="performance_test-aud-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="performance_test-aud-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_performance_test_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_performance_tests(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "performance_test_started" in actions


async def test_performance_test_completed_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(client, email="performance_test-audit-done@example.com", username="performaadn")
    workspace = await create_workspace(client, tokens["access_token"], slug="performance_test-aud2-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="performance_test-aud2-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_performance_test_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_performance_tests(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "performance_test_completed" in actions
    assert "performance_test_validated" in actions



async def test_performance_test_validation_failure_returns_422(client):
    _, tokens = await create_authenticated_user(client, email="performance_test-audit-fail@example.com", username="performaafl")
    workspace = await create_workspace(client, tokens["access_token"], slug="performance_test-aud-fail-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="performance_test-aud-fail-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_performance_test_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_performance_test_output()
    data = invalid.model_dump(mode="json")
    data["load_test_plan"] = data["load_test_plan"][:1]
    invalid_output = PerformanceTestOutput(**data)
    with patch_performance_test_agent():
        with patch("app.services.performance_test.PerformanceTestAgent.run", new=AsyncMock(return_value=(invalid_output, 50))):
            response = await client.post(
                "/v1/agents/performance-tests/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
