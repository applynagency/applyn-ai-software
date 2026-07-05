from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.backend_execution import (
    BackendExecutionArtifactResponse,
    BackendExecutionRunListResponse,
    BackendExecutionRunRequest,
    BackendExecutionRunResponse,
)
from app.services.backend_execution import BackendExecutionService

router = APIRouter(prefix="/agents/backend-execution", tags=["Backend Execution"])


@router.post("/run", response_model=BackendExecutionRunResponse, status_code=201)
async def run_backend_execution_agent(
    data: BackendExecutionRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Backend Execution agent against Backend V3 and Code Review outputs.

    Requires completed Backend Developer V3 and Backend Code Review runs unless
    explicit run IDs are specified.
    """
    service = BackendExecutionService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=BackendExecutionRunResponse)
async def get_backend_execution_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = BackendExecutionService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=BackendExecutionArtifactResponse)
async def get_backend_execution_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = BackendExecutionService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=BackendExecutionRunListResponse)
async def list_backend_execution_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    service = BackendExecutionService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
