from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models.audit import AuditLog
from app.schemas.unit_test import UnitTestGeneratorOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    mock_unit_test_generator_output,
    patch_unit_test_generator_agent,
    run_qa_architect,
    run_unit_tests,
    setup_qa_architect_pipeline,
)


async def test_unit_test_started_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="ut-audit-start@example.com", username="utauditstart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ut-aud-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ut-aud-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_qa_architect(client, tokens["access_token"], requirement["id"])
    created = await run_unit_tests(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "unit_test_started" in actions


async def test_unit_test_completed_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="ut-audit-done@example.com", username="utauditdone"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ut-aud2-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ut-aud2-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_qa_architect(client, tokens["access_token"], requirement["id"])
    created = await run_unit_tests(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "unit_test_completed" in actions
    assert "unit_test_validated" in actions


async def test_unit_test_validation_failure_returns_422(client):
    _, tokens = await create_authenticated_user(
        client, email="ut-audit-fail@example.com", username="utauditfail"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="ut-aud-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="ut-aud-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    await run_qa_architect(client, tokens["access_token"], requirement["id"])
    invalid = mock_unit_test_generator_output()
    data = invalid.model_dump()
    data["backend_unit_test_specifications"] = data["backend_unit_test_specifications"][:2]
    invalid_output = UnitTestGeneratorOutput(**data)
    with patch_unit_test_generator_agent():
        with patch(
            "app.services.unit_test_generator.UnitTestGeneratorAgent.run",
            new=AsyncMock(return_value=(invalid_output, 40)),
        ):
            response = await client.post(
                "/v1/agents/unit-tests/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
