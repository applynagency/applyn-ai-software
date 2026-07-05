from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.frontend_execution import (
    FrontendExecutionArtifactResponse,
    FrontendExecutionRunListResponse,
    FrontendExecutionRunRequest,
    FrontendExecutionRunResponse,
)
from app.services.frontend_execution import FrontendExecutionService

router = APIRouter(prefix="/agents/frontend-execution", tags=["Frontend Execution"])


@router.post("/run", response_model=FrontendExecutionRunResponse, status_code=201)
async def run_frontend_execution_agent(
    data: FrontendExecutionRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Frontend Execution agent against Frontend V3 and Code Review outputs.

    Requires completed Frontend Developer V3 and Frontend Code Review runs unless
    explicit run IDs are specified.
    """
    service = FrontendExecutionService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=FrontendExecutionRunResponse)
async def get_frontend_execution_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = FrontendExecutionService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=FrontendExecutionArtifactResponse)
async def get_frontend_execution_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = FrontendExecutionService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=FrontendExecutionRunListResponse)
async def list_frontend_execution_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    service = FrontendExecutionService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
