from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.observability_agent import (
    ObservabilityArtifactResponse,
    ObservabilityRunListResponse,
    ObservabilityRunRequest,
    ObservabilityRunResponse,
)
from app.services.observability import ObservabilityService

router = APIRouter(prefix="/agents/observability", tags=["Observability"])


@router.post("/run", response_model=ObservabilityRunResponse, status_code=201)
async def run_observability_agent(
    data: ObservabilityRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Observability Agent against a requirement and its Kubernetes manifest plan.

    Requires a completed Kubernetes run for the same requirement unless a run ID is specified.
    """
    service = ObservabilityService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=ObservabilityRunResponse)
async def get_observability_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = ObservabilityService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=ObservabilityArtifactResponse)
async def get_observability_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = ObservabilityService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=ObservabilityRunListResponse)
async def list_observability_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List Observability run history for a requirement."""
    service = ObservabilityService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
