from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.security_test import (
    SecurityTestArtifactResponse,
    SecurityTestRunListResponse,
    SecurityTestRunRequest,
    SecurityTestRunResponse,
)
from app.services.security_test import SecurityTestService

router = APIRouter(prefix="/agents/security-tests", tags=["Security Tests"])


@router.post("/run", response_model=SecurityTestRunResponse, status_code=201)
async def run_security_test_agent(
    data: SecurityTestRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Security Test agent against requirement and execution outputs.

    Requires completed Frontend Execution and Backend Execution runs for the same
    requirement unless explicit run IDs are provided. Integration Test input is optional.
    """
    service = SecurityTestService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=SecurityTestRunResponse)
async def get_security_test_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = SecurityTestService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=SecurityTestArtifactResponse)
async def get_security_test_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = SecurityTestService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=SecurityTestRunListResponse)
async def list_security_test_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List Security Test run history for a requirement."""
    service = SecurityTestService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
