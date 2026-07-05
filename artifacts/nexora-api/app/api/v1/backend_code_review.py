from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.backend_code_review import (
    BackendCodeReviewArtifactResponse,
    BackendCodeReviewRunListResponse,
    BackendCodeReviewRunRequest,
    BackendCodeReviewRunResponse,
)
from app.services.backend_code_review import BackendCodeReviewService

router = APIRouter(prefix="/agents/backend-code-review", tags=["Backend Code Review"])


@router.post("/run", response_model=BackendCodeReviewRunResponse, status_code=201)
async def run_backend_code_review_agent(
    data: BackendCodeReviewRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Backend Code Review agent against a requirement and Backend V3 output.

    Requires a completed Backend Developer V3 run for the same requirement unless
    backend_v3_run_id is specified.
    """
    service = BackendCodeReviewService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=BackendCodeReviewRunResponse)
async def get_backend_code_review_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = BackendCodeReviewService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=BackendCodeReviewArtifactResponse)
async def get_backend_code_review_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = BackendCodeReviewService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=BackendCodeReviewRunListResponse)
async def list_backend_code_review_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    service = BackendCodeReviewService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
