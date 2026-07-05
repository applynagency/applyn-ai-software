from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.performance_test import (
    PerformanceTestArtifactResponse,
    PerformanceTestRunListResponse,
    PerformanceTestRunRequest,
    PerformanceTestRunResponse,
)
from app.services.performance_test import PerformanceTestService

router = APIRouter(prefix="/agents/performance-tests", tags=["Performance Tests"])


@router.post("/run", response_model=PerformanceTestRunResponse, status_code=201)
async def run_performance_test_agent(
    data: PerformanceTestRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Performance Test agent against requirement and QA chain outputs.

    Requires a completed Integration Test run for the same requirement unless
    integration_test_run_id is specified. Security input is optional.
    """
    service = PerformanceTestService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=PerformanceTestRunResponse)
async def get_performance_test_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = PerformanceTestService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=PerformanceTestArtifactResponse)
async def get_performance_test_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = PerformanceTestService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=PerformanceTestRunListResponse)
async def list_performance_test_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List Performance Test run history for a requirement."""
    service = PerformanceTestService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
