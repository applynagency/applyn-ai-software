from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.frontend_v3 import (
    FrontendV3ArtifactResponse,
    FrontendV3RunListResponse,
    FrontendV3RunRequest,
    FrontendV3RunResponse,
)
from app.services.frontend_v3 import FrontendDeveloperV3Service

router = APIRouter(prefix="/agents/frontend-v3", tags=["Frontend Developer V3"])


@router.post("/run", response_model=FrontendV3RunResponse, status_code=201)
async def run_frontend_v3_agent(
    data: FrontendV3RunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Frontend Developer V3 agent against a requirement and Frontend V2 output.

    Requires a completed Frontend Developer V2 run for the same requirement unless
    frontend_v2_run_id is specified.
    """
    service = FrontendDeveloperV3Service(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=FrontendV3RunResponse)
async def get_frontend_v3_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = FrontendDeveloperV3Service(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=FrontendV3ArtifactResponse)
async def get_frontend_v3_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = FrontendDeveloperV3Service(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=FrontendV3RunListResponse)
async def list_frontend_v3_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    service = FrontendDeveloperV3Service(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
