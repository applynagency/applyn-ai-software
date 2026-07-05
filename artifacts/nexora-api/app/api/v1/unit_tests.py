from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.unit_test import (
    UnitTestArtifactResponse,
    UnitTestRunListResponse,
    UnitTestRunRequest,
    UnitTestRunResponse,
)
from app.services.unit_test_generator import UnitTestGeneratorService

router = APIRouter(prefix="/agents/unit-tests", tags=["Unit Tests"])


@router.post("/run", response_model=UnitTestRunResponse, status_code=201)
async def run_unit_test_generator_agent(
    data: UnitTestRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Unit Test Generator agent against a requirement and QA Architect output.

    Requires a completed QA Architect run for the same requirement unless
    qa_architect_run_id is specified.
    """
    service = UnitTestGeneratorService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=UnitTestRunResponse)
async def get_unit_test_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = UnitTestGeneratorService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=UnitTestArtifactResponse)
async def get_unit_test_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = UnitTestGeneratorService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=UnitTestRunListResponse)
async def list_unit_test_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List Unit Test Generator run history for a requirement."""
    service = UnitTestGeneratorService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
