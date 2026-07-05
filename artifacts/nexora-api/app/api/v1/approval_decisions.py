from fastapi import APIRouter

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.approval import ApprovalDecisionRequest, ApprovalRunResponse
from app.services.approval import ApprovalWorkflowService

router = APIRouter(prefix="/approval", tags=["Approval Decisions"])


@router.post("/{artifact_id}/approve", response_model=ApprovalRunResponse)
async def approve_artifact(
    artifact_id: str,
    data: ApprovalDecisionRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """Grant human approval for deployment readiness."""
    service = ApprovalWorkflowService(session)
    return await service.approve_artifact(artifact_id, data, current_user, org_context)


@router.post("/{artifact_id}/reject", response_model=ApprovalRunResponse)
async def reject_artifact(
    artifact_id: str,
    data: ApprovalDecisionRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """Reject deployment readiness and block downstream deployment."""
    service = ApprovalWorkflowService(session)
    return await service.reject_artifact(artifact_id, data, current_user, org_context)
