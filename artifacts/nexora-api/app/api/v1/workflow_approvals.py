"""API for Workflow Human Approval Gates (Sprint 38C).

Customer-facing, additive. Approving resumes the paused workflow through the
existing 38A engine; rejecting fails the run. No autonomous/auto-approval logic.
"""

from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.ai_team import (
    AITeamWorkflowApprovalDecisionRequest,
    AITeamWorkflowApprovalListResponse,
    AITeamWorkflowApprovalResponse,
    AITeamWorkflowExecuteResponse,
)
from app.services.ai_team_workflow import AITeamWorkflowService

router = APIRouter(tags=["AI Team Workflow Approvals"])


@router.get("/workflow-approvals", response_model=AITeamWorkflowApprovalListResponse)
async def list_workflow_approvals(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    workflow_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
):
    service = AITeamWorkflowService(session)
    return await service.list_approvals(
        current_user, org_context, workflow_id=workflow_id, status=status,
        offset=offset, limit=limit,
    )


@router.get("/workflow-approvals/{approval_id}", response_model=AITeamWorkflowApprovalResponse)
async def get_workflow_approval(
    approval_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamWorkflowService(session)
    return await service.get_approval(approval_id, current_user, org_context)


@router.post(
    "/workflow-approvals/{approval_id}/approve",
    response_model=AITeamWorkflowExecuteResponse,
)
async def approve_workflow_approval(
    approval_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    data: AITeamWorkflowApprovalDecisionRequest | None = None,
):
    service = AITeamWorkflowService(session)
    comments = data.comments if data else None
    return await service.approve(approval_id, comments, current_user, org_context)


@router.post(
    "/workflow-approvals/{approval_id}/reject",
    response_model=AITeamWorkflowApprovalResponse,
)
async def reject_workflow_approval(
    approval_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    data: AITeamWorkflowApprovalDecisionRequest | None = None,
):
    service = AITeamWorkflowService(session)
    comments = data.comments if data else None
    return await service.reject(approval_id, comments, current_user, org_context)


@router.get(
    "/workflow-runs/{run_id}/approvals",
    response_model=AITeamWorkflowApprovalListResponse,
)
async def list_run_approvals(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamWorkflowService(session)
    return await service.list_run_approvals(run_id, current_user, org_context)
