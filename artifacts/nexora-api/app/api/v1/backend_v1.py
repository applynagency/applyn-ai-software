from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.backend_v1 import (
    BackendV1ArtifactResponse,
    BackendV1RunListResponse,
    BackendV1RunRequest,
    BackendV1RunResponse,
)
from app.services.backend_v1 import BackendDeveloperV1Service

router = APIRouter(prefix="/agents/backend-v1", tags=["Backend Developer V1"])


@router.post("/run", response_model=BackendV1RunResponse, status_code=201)
async def run_backend_v1_agent(
    data: BackendV1RunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Backend Developer V1 agent against a requirement and Backend Architect output.

    Requires a completed Backend Architect run for the same requirement unless
    backend_architect_run_id is specified.
    """
    service = BackendDeveloperV1Service(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=BackendV1RunResponse)
async def get_backend_v1_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = BackendDeveloperV1Service(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=BackendV1ArtifactResponse)
async def get_backend_v1_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = BackendDeveloperV1Service(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=BackendV1RunListResponse)
async def list_backend_v1_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List Backend Developer V1 run history for a requirement."""
    service = BackendDeveloperV1Service(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
