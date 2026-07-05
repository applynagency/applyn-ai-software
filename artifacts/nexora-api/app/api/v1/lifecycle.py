from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.lifecycle.orchestrator import LifecycleOrchestratorService
from app.schemas.lifecycle import (
    ApplicationVersionResponse,
    ChangeRequestCreate,
    ChangeRequestDecision,
    ImpactAnalysisRequest,
    RegenerationRunListResponse,
    RegenerationRunResponse,
    ReleaseCreate,
    ReleaseHistoryListResponse,
    ReleaseHistoryResponse,
)
from app.services.lifecycle import LifecycleService

router = APIRouter(tags=["Lifecycle"])


@router.post("/change-requests", response_model=RegenerationRunResponse, status_code=201)
async def create_change_request(
    data: ChangeRequestCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    orchestrator = LifecycleOrchestratorService(session)
    return await orchestrator.create_change_request(data, current_user, org_context)


@router.get("/change-requests/{run_id}", response_model=RegenerationRunResponse)
async def get_change_request(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = LifecycleService(session)
    return await service.get_regeneration_run(run_id, current_user, org_context)


@router.get("/change-requests", response_model=RegenerationRunListResponse)
async def list_change_requests(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    requirement_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    service = LifecycleService(session)
    return await service.list_change_requests(
        current_user, org_context, requirement_id=requirement_id, offset=offset, limit=limit
    )


@router.post("/change-requests/{run_id}/submit", response_model=RegenerationRunResponse)
async def submit_change_request(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = LifecycleService(session)
    result = await service.submit_change_request(run_id, current_user, org_context)
    await session.commit()
    return result


@router.post("/change-requests/{run_id}/decide", response_model=RegenerationRunResponse)
async def decide_change_request(
    run_id: str,
    decision: ChangeRequestDecision,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = LifecycleService(session)
    result = await service.decide_change_request(run_id, decision, current_user, org_context)
    await session.commit()
    return result


@router.post("/impact-analysis", response_model=RegenerationRunResponse)
async def recompute_impact_analysis(
    data: ImpactAnalysisRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = LifecycleService(session)
    return await service.recompute_impact(data.regeneration_run_id, current_user, org_context)


@router.get("/impact-analysis/{run_id}", response_model=RegenerationRunResponse)
async def get_impact_analysis(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = LifecycleService(session)
    return await service.get_regeneration_run(run_id, current_user, org_context)


@router.post("/regeneration", response_model=RegenerationRunResponse)
async def execute_regeneration(
    data: ImpactAnalysisRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    orchestrator = LifecycleOrchestratorService(session)
    return await orchestrator.regenerate_version(
        data.regeneration_run_id, current_user, org_context
    )


@router.get("/regeneration/{run_id}", response_model=RegenerationRunResponse)
async def get_regeneration(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = LifecycleService(session)
    return await service.get_regeneration_run(run_id, current_user, org_context)


@router.get("/releases", response_model=ReleaseHistoryListResponse)
async def list_releases(
    project_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    service = LifecycleService(session)
    return await service.list_releases(
        project_id, current_user, org_context, offset=offset, limit=limit
    )


@router.post("/releases", response_model=ReleaseHistoryResponse, status_code=201)
async def create_release(
    data: ReleaseCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    orchestrator = LifecycleOrchestratorService(session)
    return await orchestrator.create_release(data, current_user, org_context)


@router.get("/application-versions", response_model=list[ApplicationVersionResponse])
async def list_application_versions(
    project_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    service = LifecycleService(session)
    return await service.list_versions(
        project_id, current_user, org_context, offset=offset, limit=limit
    )
