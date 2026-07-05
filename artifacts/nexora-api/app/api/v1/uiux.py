from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.uiux_designer import (
    UIUXArtifactResponse,
    UIUXRunListResponse,
    UIUXRunRequest,
    UIUXRunResponse,
)
from app.services.uiux_designer import UIUXDesignerService

router = APIRouter(prefix="/agents/uiux", tags=["UI/UX Designer"])


@router.post("/run", response_model=UIUXRunResponse, status_code=201)
async def run_uiux_designer_agent(
    data: UIUXRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the UI/UX Designer agent against a requirement and Business Analyst output.

    Requires a completed Business Analyst run for the same requirement unless
    business_analyst_run_id is specified.
    """
    service = UIUXDesignerService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=UIUXRunResponse)
async def get_uiux_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = UIUXDesignerService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=UIUXArtifactResponse)
async def get_uiux_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = UIUXDesignerService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=UIUXRunListResponse)
async def list_uiux_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List UI/UX Designer run history for a requirement."""
    service = UIUXDesignerService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
