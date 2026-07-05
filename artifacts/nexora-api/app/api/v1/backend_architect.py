from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.backend_architect import (
    BackendArchitectArtifactResponse,
    BackendArchitectRunListResponse,
    BackendArchitectRunRequest,
    BackendArchitectRunResponse,
)
from app.services.backend_architect import BackendArchitectService

router = APIRouter(prefix="/agents/backend-architect", tags=["Backend Architect"])


@router.post("/run", response_model=BackendArchitectRunResponse, status_code=201)
async def run_backend_architect_agent(
    data: BackendArchitectRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Backend Architect agent against a requirement and Business Analyst output.

    Requires a completed Business Analyst run for the same requirement unless
    business_analyst_run_id is specified.
    """
    service = BackendArchitectService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=BackendArchitectRunResponse)
async def get_backend_architect_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = BackendArchitectService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=BackendArchitectArtifactResponse)
async def get_backend_architect_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = BackendArchitectService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=BackendArchitectRunListResponse)
async def list_backend_architect_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List Backend Architect run history for a requirement."""
    service = BackendArchitectService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
