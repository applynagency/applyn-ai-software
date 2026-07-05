from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.approval import (
    ApprovalArtifactResponse,
    ApprovalRunListResponse,
    ApprovalRunRequest,
    ApprovalRunResponse,
)
from app.services.approval import ApprovalWorkflowService

router = APIRouter(prefix="/agents/approval", tags=["Approval Workflow"])


@router.post("/run", response_model=ApprovalRunResponse, status_code=201)
async def run_approval_workflow_agent(
    data: ApprovalRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Generate an approval package for human review after Full Stack Assembly.

    Deployment requires approval_status == APPROVED via the approve endpoint.
    """
    service = ApprovalWorkflowService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=ApprovalRunResponse)
async def get_approval_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = ApprovalWorkflowService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=ApprovalArtifactResponse)
async def get_approval_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = ApprovalWorkflowService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=ApprovalRunListResponse)
async def list_approval_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    service = ApprovalWorkflowService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
