from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.frontend_v2 import (
    FrontendV2ArtifactResponse,
    FrontendV2RunListResponse,
    FrontendV2RunRequest,
    FrontendV2RunResponse,
)
from app.services.frontend_v2 import FrontendDeveloperV2Service

router = APIRouter(prefix="/agents/frontend-v2", tags=["Frontend Developer V2"])


@router.post("/run", response_model=FrontendV2RunResponse, status_code=201)
async def run_frontend_v2_agent(
    data: FrontendV2RunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Frontend Developer V2 agent against a requirement and Frontend V1 output.

    Requires a completed Frontend Developer V1 run for the same requirement unless
    frontend_v1_run_id is specified.
    """
    service = FrontendDeveloperV2Service(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=FrontendV2RunResponse)
async def get_frontend_v2_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = FrontendDeveloperV2Service(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=FrontendV2ArtifactResponse)
async def get_frontend_v2_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = FrontendDeveloperV2Service(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=FrontendV2RunListResponse)
async def list_frontend_v2_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List Frontend Developer V2 run history for a requirement."""
    service = FrontendDeveloperV2Service(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
