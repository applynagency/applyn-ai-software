from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.integration_test import (
    IntegrationTestArtifactResponse,
    IntegrationTestRunListResponse,
    IntegrationTestRunRequest,
    IntegrationTestRunResponse,
)
from app.services.integration_test import IntegrationTestService

router = APIRouter(prefix="/agents/integration-tests", tags=["Integration Tests"])


@router.post("/run", response_model=IntegrationTestRunResponse, status_code=201)
async def run_integration_test_agent(
    data: IntegrationTestRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Integration Test agent against requirement and execution outputs.

    Requires completed Frontend Execution, Backend Execution, and Unit Test runs
    for the same requirement unless explicit run IDs are provided.
    """
    service = IntegrationTestService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=IntegrationTestRunResponse)
async def get_integration_test_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = IntegrationTestService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=IntegrationTestArtifactResponse)
async def get_integration_test_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = IntegrationTestService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=IntegrationTestRunListResponse)
async def list_integration_test_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List Integration Test run history for a requirement."""
    service = IntegrationTestService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
