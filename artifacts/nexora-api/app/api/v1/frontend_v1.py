from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.frontend_v1 import (
    FrontendV1ArtifactResponse,
    FrontendV1RunListResponse,
    FrontendV1RunRequest,
    FrontendV1RunResponse,
)
from app.services.frontend_v1 import FrontendDeveloperV1Service

router = APIRouter(prefix="/agents/frontend-v1", tags=["Frontend Developer V1"])


@router.post("/run", response_model=FrontendV1RunResponse, status_code=201)
async def run_frontend_v1_agent(
    data: FrontendV1RunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Frontend Developer V1 agent against a requirement and Frontend Architect output.

    Requires a completed Frontend Architect run for the same requirement unless
    frontend_architect_run_id is specified.
    """
    service = FrontendDeveloperV1Service(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=FrontendV1RunResponse)
async def get_frontend_v1_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = FrontendDeveloperV1Service(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=FrontendV1ArtifactResponse)
async def get_frontend_v1_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = FrontendDeveloperV1Service(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=FrontendV1RunListResponse)
async def list_frontend_v1_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List Frontend Developer V1 run history for a requirement."""
    service = FrontendDeveloperV1Service(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
