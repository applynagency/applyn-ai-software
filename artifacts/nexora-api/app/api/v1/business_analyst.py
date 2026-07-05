from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.business_analyst import (
    BusinessAnalystArtifactResponse,
    BusinessAnalystRunListResponse,
    BusinessAnalystRunRequest,
    BusinessAnalystRunResponse,
)
from app.services.business_analyst import BusinessAnalystService

router = APIRouter(prefix="/agents/business-analyst", tags=["Business Analyst"])


@router.post("/run", response_model=BusinessAnalystRunResponse, status_code=201)
async def run_business_analyst_agent(
    data: BusinessAnalystRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Business Analyst agent against a requirement and Product Owner output.

    Requires a completed Product Owner run for the same requirement unless
    product_owner_run_id is specified.
    """
    service = BusinessAnalystService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=BusinessAnalystRunResponse)
async def get_business_analyst_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = BusinessAnalystService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=BusinessAnalystArtifactResponse)
async def get_business_analyst_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = BusinessAnalystService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=BusinessAnalystRunListResponse)
async def list_business_analyst_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List Business Analyst run history for a requirement."""
    service = BusinessAnalystService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
