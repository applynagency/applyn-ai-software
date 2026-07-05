from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.cicd_agent import (
    CicdArtifactResponse,
    CicdRunListResponse,
    CicdRunRequest,
    CicdRunResponse,
)
from app.services.cicd import CicdService

router = APIRouter(prefix="/agents/cicd", tags=["CI/CD"])


@router.post("/run", response_model=CicdRunResponse, status_code=201)
async def run_cicd_agent(
    data: CicdRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the CI/CD Agent against a requirement and Docker containerization output.

    Requires a completed Docker Agent run for the same requirement unless a run ID is specified.
    """
    service = CicdService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=CicdRunResponse)
async def get_cicd_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = CicdService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=CicdArtifactResponse)
async def get_cicd_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = CicdService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=CicdRunListResponse)
async def list_cicd_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List CI/CD run history for a requirement."""
    service = CicdService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
