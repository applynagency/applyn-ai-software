from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models.audit import AuditLog
from app.schemas.qa_architect import QAArchitectOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    mock_qa_architect_output,
    patch_qa_architect_agent,
    run_qa_architect,
    setup_qa_architect_pipeline,
)


async def test_qa_architect_started_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="qa-audit-start@example.com", username="qaauditstart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="qa-aud-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="qa-aud-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_qa_architect(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "qa_architect_started" in actions


async def test_qa_architect_completed_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="qa-audit-done@example.com", username="qaauditdone"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="qa-aud2-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="qa-aud2-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_qa_architect(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "qa_architect_completed" in actions
    assert "qa_architect_validated" in actions


async def test_qa_architect_validation_failure_returns_422(client):
    _, tokens = await create_authenticated_user(
        client, email="qa-audit-fail@example.com", username="qaauditfail"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="qa-aud-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="qa-aud-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_qa_architect_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_qa_architect_output()
    data = invalid.model_dump()
    data["test_coverage_matrix"] = data["test_coverage_matrix"][:1]
    invalid_output = QAArchitectOutput(**data)
    with patch_qa_architect_agent():
        with patch(
            "app.services.qa_architect.QAArchitectAgent.run",
            new=AsyncMock(return_value=(invalid_output, 50)),
        ):
            response = await client.post(
                "/v1/agents/qa-architect/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
