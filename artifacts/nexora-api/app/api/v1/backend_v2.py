from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.backend_v2 import (
    BackendV2ArtifactResponse,
    BackendV2RunListResponse,
    BackendV2RunRequest,
    BackendV2RunResponse,
)
from app.services.backend_v2 import BackendDeveloperV2Service

router = APIRouter(prefix="/agents/backend-v2", tags=["Backend Developer V2"])


@router.post("/run", response_model=BackendV2RunResponse, status_code=201)
async def run_backend_v2_agent(
    data: BackendV2RunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Backend Developer V2 agent against a requirement and Backend V1 output.

    Requires a completed Backend Developer V1 run for the same requirement unless
    backend_v1_run_id is specified.
    """
    service = BackendDeveloperV2Service(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=BackendV2RunResponse)
async def get_backend_v2_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = BackendDeveloperV2Service(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=BackendV2ArtifactResponse)
async def get_backend_v2_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = BackendDeveloperV2Service(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=BackendV2RunListResponse)
async def list_backend_v2_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List Backend Developer V2 run history for a requirement."""
    service = BackendDeveloperV2Service(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
