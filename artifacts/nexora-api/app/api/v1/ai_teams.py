"""API for Custom AI Teams (Sprint 37A).

Customer-facing AI Workforce. Strictly additive — does not touch the internal
APPYLN software-generation pipeline.
"""

from fastapi import APIRouter, File, Query, UploadFile

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.models.ai_team import AITeamStatus
from app.schemas.ai_team import (
    AITeamCreate,
    AITeamDocumentListResponse,
    AITeamDocumentResponse,
    AITeamExecuteRequest,
    AITeamExecuteResponse,
    AITeamListResponse,
    AITeamResponse,
    AITeamRunListResponse,
    AITeamRunResponse,
    AITeamUpdate,
)
from app.services.ai_team import AITeamService

router = APIRouter(prefix="/ai-teams", tags=["AI Teams"])


@router.get("", response_model=AITeamListResponse)
async def list_ai_teams(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    status: AITeamStatus | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    service = AITeamService(session)
    return await service.list_teams(
        current_user, org_context, status=status, offset=offset, limit=limit
    )


@router.post("", response_model=AITeamResponse, status_code=201)
async def create_ai_team(
    data: AITeamCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamService(session)
    return await service.create_team(data, current_user, org_context)


# --- Knowledge Base (Sprint 37D) ------------------------------------------
# Declared before "/{team_id}" so the literal "documents" segment is unambiguous.
@router.delete("/documents/{document_id}", status_code=204)
async def delete_ai_team_document(
    document_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamService(session)
    await service.delete_document(document_id, current_user, org_context)


@router.post("/{team_id}/documents", response_model=AITeamDocumentResponse, status_code=201)
async def upload_ai_team_document(
    team_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    file: UploadFile = File(...),
):
    service = AITeamService(session)
    data = await file.read()
    return await service.upload_document(
        team_id,
        filename=file.filename or "document",
        content_type=file.content_type or "application/octet-stream",
        data=data,
        current_user=current_user,
        org_context=org_context,
    )


@router.get("/{team_id}/documents", response_model=AITeamDocumentListResponse)
async def list_ai_team_documents(
    team_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
):
    service = AITeamService(session)
    return await service.list_documents(
        team_id, current_user, org_context, offset=offset, limit=limit
    )


# --- Multi-agent collaboration (Sprint 37C) -------------------------------
# Declared before "/{team_id}" so the literal "runs" segment is unambiguous.
@router.get("/runs/{run_id}", response_model=AITeamRunResponse)
async def get_ai_team_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamService(session)
    return await service.get_team_run(run_id, current_user, org_context)


@router.post("/{team_id}/execute", response_model=AITeamExecuteResponse)
async def execute_ai_team(
    team_id: str,
    data: AITeamExecuteRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamService(session)
    return await service.execute_team(team_id, data.prompt, current_user, org_context)


@router.get("/{team_id}/runs", response_model=AITeamRunListResponse)
async def list_ai_team_runs(
    team_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    service = AITeamService(session)
    return await service.list_team_runs(
        team_id, current_user, org_context, offset=offset, limit=limit
    )


@router.get("/{team_id}", response_model=AITeamResponse)
async def get_ai_team(
    team_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamService(session)
    return await service.get_team(team_id, current_user, org_context)


@router.put("/{team_id}", response_model=AITeamResponse)
async def update_ai_team(
    team_id: str,
    data: AITeamUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamService(session)
    return await service.update_team(team_id, data, current_user, org_context)


@router.delete("/{team_id}", status_code=204)
async def delete_ai_team(
    team_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = AITeamService(session)
    await service.delete_team(team_id, current_user, org_context)
