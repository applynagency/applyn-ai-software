from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.fullstack_assembly import (
    FullstackAssemblyArtifactResponse,
    FullstackAssemblyRunListResponse,
    FullstackAssemblyRunRequest,
    FullstackAssemblyRunResponse,
)
from app.services.fullstack_assembly import FullStackAssemblyService

router = APIRouter(prefix="/agents/fullstack-assembly", tags=["Full Stack Assembly"])


@router.post("/run", response_model=FullstackAssemblyRunResponse, status_code=201)
async def run_fullstack_assembly_agent(
    data: FullstackAssemblyRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Assemble a deployable application package from Frontend Execution output.

    Backend execution artifacts are optional and will be integrated when available.
    """
    service = FullStackAssemblyService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=FullstackAssemblyRunResponse)
async def get_fullstack_assembly_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = FullStackAssemblyService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=FullstackAssemblyArtifactResponse)
async def get_fullstack_assembly_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = FullStackAssemblyService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=FullstackAssemblyRunListResponse)
async def list_fullstack_assembly_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    service = FullStackAssemblyService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
