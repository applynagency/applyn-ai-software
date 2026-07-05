from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.frontend_code_review import (
    FrontendCodeReviewArtifactResponse,
    FrontendCodeReviewRunListResponse,
    FrontendCodeReviewRunRequest,
    FrontendCodeReviewRunResponse,
)
from app.services.frontend_code_review import FrontendCodeReviewService

router = APIRouter(prefix="/agents/frontend-code-review", tags=["Frontend Code Review"])


@router.post("/run", response_model=FrontendCodeReviewRunResponse, status_code=201)
async def run_frontend_code_review_agent(
    data: FrontendCodeReviewRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Frontend Code Review agent against a requirement and Frontend V3 output.

    Requires a completed Frontend Developer V3 run for the same requirement unless
    frontend_v3_run_id is specified.
    """
    service = FrontendCodeReviewService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=FrontendCodeReviewRunResponse)
async def get_frontend_code_review_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = FrontendCodeReviewService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=FrontendCodeReviewArtifactResponse)
async def get_frontend_code_review_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = FrontendCodeReviewService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=FrontendCodeReviewRunListResponse)
async def list_frontend_code_review_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    service = FrontendCodeReviewService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
