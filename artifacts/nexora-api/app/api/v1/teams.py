
from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.models.team import TeamStatus, TeamType
from app.schemas.team import (
    TeamAuditListResponse,
    TeamCreate,
    TeamDuplicateResponse,
    TeamListResponse,
    TeamResponse,
    TeamResponsibilityCreate,
    TeamResponsibilityResponse,
    TeamUpdate,
)
from app.services.team import TeamService
from app.services.team_responsibility import TeamResponsibilityService

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get("", response_model=TeamListResponse)
async def list_teams(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    team_type: TeamType | None = Query(default=None),
    status: TeamStatus | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    service = TeamService(session)
    return await service.list_for_organization(
        current_user,
        org_context,
        team_type=team_type,
        status=status,
        offset=offset,
        limit=limit,
    )


@router.post("", response_model=TeamResponse, status_code=201)
async def create_team(
    data: TeamCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = TeamService(session)
    return await service.create(data, current_user, org_context)


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = TeamService(session)
    return await service.get(team_id, current_user, org_context)


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: str,
    data: TeamUpdate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = TeamService(session)
    return await service.update(team_id, data, current_user, org_context)


@router.delete("/{team_id}", status_code=204)
async def delete_team(
    team_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = TeamService(session)
    await service.delete(team_id, current_user, org_context)


@router.post("/{team_id}/duplicate", response_model=TeamDuplicateResponse)
async def duplicate_team(
    team_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = TeamService(session)
    return await service.duplicate(team_id, current_user, org_context)


@router.post("/{team_id}/archive", response_model=TeamResponse)
async def archive_team(
    team_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = TeamService(session)
    return await service.archive(team_id, current_user, org_context)


@router.get("/{team_id}/audit", response_model=TeamAuditListResponse)
async def list_team_audit_events(
    team_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = TeamService(session)
    return await service.list_audit_events(team_id, current_user, org_context)


@router.post("/{team_id}/responsibilities", response_model=TeamResponsibilityResponse, status_code=201)
async def create_team_responsibility(
    team_id: str,
    data: TeamResponsibilityCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = TeamResponsibilityService(session)
    return await service.create(team_id, data, current_user, org_context)
