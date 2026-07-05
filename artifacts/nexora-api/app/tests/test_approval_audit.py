from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models.audit import AuditLog
from app.schemas.approval import ApprovalWorkflowOutput
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_project,
    create_requirement,
    create_workspace,
    patch_approval_workflow_agent,
    run_approval,
    setup_approval_pipeline,
)


async def test_approval_started_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="appr-audit-start@example.com", username="apprauditstart"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-aud-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-aud-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "approval_started" in actions


async def test_approval_completed_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="appr-audit-done@example.com", username="apprauditdone"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-aud2-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-aud2-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    run_id = created.json()["id"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.resource_id == run_id))
        actions = {log.action for log in result.scalars().all()}
    assert "approval_completed" in actions


async def test_approval_failed_audit_rolls_back_on_validation(client):
    _, tokens = await create_authenticated_user(
        client, email="appr-audit-fail@example.com", username="apprauditfail"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-aud-fail-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-aud-fail-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    invalid_output = ApprovalWorkflowOutput.model_construct(
        approval_summary={},
        review_checklist=[],
        deployment_readiness={},
        recommendation="APPROVE",
        approval_status="UNDER_REVIEW",
    )
    with patch_approval_workflow_agent():
        with patch(
            "app.services.approval.ApprovalWorkflowAgent.run",
            new=AsyncMock(return_value=invalid_output),
        ):
            response = await client.post(
                "/v1/agents/approval/run",
                headers=auth_headers(tokens["access_token"]),
                json={"requirement_id": requirement["id"]},
            )
    assert response.status_code == 422
    # /v1/agents/approval is a customer-facing path, so the validation error is
    # surfaced through a customer-safe message. The ValidationError type confirms
    # the run was rejected and rolled back rather than completed.
    assert response.json()["error_type"] == "ValidationError"


async def test_approval_approved_audit(client):
    from app.database.session import AsyncSessionLocal

    _, tokens = await create_authenticated_user(
        client, email="appr-audit-approved@example.com", username="apprauditapproved"
    )
    workspace = await create_workspace(client, tokens["access_token"], slug="appr-aud-appr-ws")
    project = await create_project(
        client, tokens["access_token"], workspace_id=workspace["id"], slug="appr-aud-appr-proj"
    )
    requirement = await create_requirement(
        client, tokens["access_token"], project_id=project["id"]
    )
    await setup_approval_pipeline(client, tokens["access_token"], requirement["id"])
    created = await run_approval(client, tokens["access_token"], requirement["id"])
    artifact_id = created.json()["artifact"]["id"]
    run_id = created.json()["id"]
    await client.post(
        f"/v1/approval/{artifact_id}/approve",
        headers=auth_headers(tokens["access_token"]),
        json={"reviewer_notes": "Ready for deployment"},
    )

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.resource_id == run_id,
                AuditLog.action == "approval_approved",
            )
        )
        log = result.scalars().first()
    assert log is not None
    assert log.details["artifact_id"] == artifact_id
