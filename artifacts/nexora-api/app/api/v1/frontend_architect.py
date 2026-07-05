from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.frontend_architect import (
    FrontendArchitectArtifactResponse,
    FrontendArchitectRunListResponse,
    FrontendArchitectRunRequest,
    FrontendArchitectRunResponse,
)
from app.services.frontend_architect import FrontendArchitectService

router = APIRouter(prefix="/agents/frontend-architect", tags=["Frontend Architect"])


@router.post("/run", response_model=FrontendArchitectRunResponse, status_code=201)
async def run_frontend_architect_agent(
    data: FrontendArchitectRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Frontend Architect agent against a requirement and UI/UX Designer output.

    Requires a completed UI/UX Designer run for the same requirement unless
    uiux_run_id is specified.
    """
    service = FrontendArchitectService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=FrontendArchitectRunResponse)
async def get_frontend_architect_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = FrontendArchitectService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=FrontendArchitectArtifactResponse)
async def get_frontend_architect_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = FrontendArchitectService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=FrontendArchitectRunListResponse)
async def list_frontend_architect_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List Frontend Architect run history for a requirement."""
    service = FrontendArchitectService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
