from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.infrastructure_architect import (
    InfrastructureArchitectArtifactResponse,
    InfrastructureArchitectRunListResponse,
    InfrastructureArchitectRunRequest,
    InfrastructureArchitectRunResponse,
)
from app.services.infrastructure_architect import InfrastructureArchitectService

router = APIRouter(prefix="/agents/infrastructure-architect", tags=["Infrastructure Architect"])


@router.post("/run", response_model=InfrastructureArchitectRunResponse, status_code=201)
async def run_infrastructure_architect_agent(
    data: InfrastructureArchitectRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Infrastructure Architect agent against a requirement and upstream outputs.

    Requires completed Frontend Execution, Backend Execution, and QA Approval runs
    for the same requirement unless run IDs are specified.
    """
    service = InfrastructureArchitectService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=InfrastructureArchitectRunResponse)
async def get_infrastructure_architect_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = InfrastructureArchitectService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=InfrastructureArchitectArtifactResponse)
async def get_infrastructure_architect_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = InfrastructureArchitectService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=InfrastructureArchitectRunListResponse)
async def list_infrastructure_architect_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List Infrastructure Architect run history for a requirement."""
    service = InfrastructureArchitectService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
