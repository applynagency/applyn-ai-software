from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models.audit import AuditLog
from app.schemas.qa_approval import QAApprovalOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    mock_qa_approval_output,
    patch_qa_approval_agent,
    run_qa_approval,
    setup_qa_approval_pipeline,
)


async def test_qa_approval_started_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(client, email="qa_approval-audit-start@example.com", username="qa_approast")
    workspace = await create_workspace(client, tokens["access_token"], slug="qa_approval-aud-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="qa_approval-aud-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_qa_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_qa_approval(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "qa_approval_started" in actions


async def test_qa_approval_completed_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(client, email="qa_approval-audit-done@example.com", username="qa_approadn")
    workspace = await create_workspace(client, tokens["access_token"], slug="qa_approval-aud2-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="qa_approval-aud2-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_qa_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_qa_approval(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "qa_approval_completed" in actions



async def test_qa_approval_validation_failure_returns_422(client):
    _, tokens = await create_authenticated_user(client, email="qa_approval-audit-fail@example.com", username="qa_approafl")
    workspace = await create_workspace(client, tokens["access_token"], slug="qa_approval-aud-fail-ws")
    project = await create_project(client, tokens["access_token"], workspace_id=workspace["id"], slug="qa_approval-aud-fail-proj")
    requirement = await create_requirement(client, tokens["access_token"], project_id=project["id"])
    await setup_qa_approval_pipeline(client, tokens["access_token"], requirement["id"])
    invalid = mock_qa_approval_output()
    data = invalid.model_dump(mode="json")
    data["findings"] = []
    invalid_output = QAApprovalOutput(**data)
    with patch_qa_approval_agent():
        with patch("app.services.qa_approval.QAApprovalAgent.run", new=AsyncMock(return_value=(invalid_output, 50))):
            response = await client.post(
                "/v1/agents/qa-approvals/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
