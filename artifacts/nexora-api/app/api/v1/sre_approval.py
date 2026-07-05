from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.sre_approval import (
    SreApprovalArtifactResponse,
    SreApprovalRunListResponse,
    SreApprovalRunRequest,
    SreApprovalRunResponse,
)
from app.services.sre_approval import SreApprovalService

router = APIRouter(prefix="/agents/sre-approval", tags=["SRE Approval"])


@router.post("/run", response_model=SreApprovalRunResponse, status_code=201)
async def run_sre_approval_agent(
    data: SreApprovalRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the SRE Approval Agent against a requirement's full DevOps operations output.

    Requires completed Kubernetes and Observability runs for the same requirement unless run
    IDs are specified.
    """
    service = SreApprovalService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=SreApprovalRunResponse)
async def get_sre_approval_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = SreApprovalService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=SreApprovalArtifactResponse)
async def get_sre_approval_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = SreApprovalService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=SreApprovalRunListResponse)
async def list_sre_approval_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List SRE Approval run history for a requirement."""
    service = SreApprovalService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
