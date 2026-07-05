from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.backend_v3 import (
    BackendV3ArtifactResponse,
    BackendV3RunListResponse,
    BackendV3RunRequest,
    BackendV3RunResponse,
)
from app.services.backend_v3 import BackendDeveloperV3Service

router = APIRouter(prefix="/agents/backend-v3", tags=["Backend Developer V3"])


@router.post("/run", response_model=BackendV3RunResponse, status_code=201)
async def run_backend_v3_agent(
    data: BackendV3RunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Backend Developer V3 agent against a requirement and Backend V2 output.

    Requires a completed Backend Developer V2 run for the same requirement unless
    backend_v2_run_id is specified.
    """
    service = BackendDeveloperV3Service(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=BackendV3RunResponse)
async def get_backend_v3_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = BackendDeveloperV3Service(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=BackendV3ArtifactResponse)
async def get_backend_v3_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = BackendDeveloperV3Service(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=BackendV3RunListResponse)
async def list_backend_v3_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    service = BackendDeveloperV3Service(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
