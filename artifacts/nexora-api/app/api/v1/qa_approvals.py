from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.qa_approval import (
    QAApprovalArtifactResponse,
    QAApprovalRunListResponse,
    QAApprovalRunRequest,
    QAApprovalRunResponse,
)
from app.services.qa_approval import QAApprovalService

router = APIRouter(prefix="/agents/qa-approvals", tags=["QA Approvals"])


@router.post("/run", response_model=QAApprovalRunResponse, status_code=201)
async def run_qa_approval_agent(
    data: QAApprovalRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the QA Approval agent against completed QA delivery chain outputs.

    Requires completed Integration, Security, and Performance runs for the same
    requirement unless explicit run IDs are provided.
    """
    service = QAApprovalService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=QAApprovalRunResponse)
async def get_qa_approval_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = QAApprovalService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=QAApprovalArtifactResponse)
async def get_qa_approval_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = QAApprovalService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=QAApprovalRunListResponse)
async def list_qa_approval_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List QA Approval run history for a requirement."""
    service = QAApprovalService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
