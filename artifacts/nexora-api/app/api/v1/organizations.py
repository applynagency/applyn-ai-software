from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.schemas.organization import (
    InvitationListResponse,
    OrganizationCreate,
    OrganizationCreatedResponse,
    OrganizationListResponse,
    OrganizationMemberCreate,
    OrganizationMemberListResponse,
    OrganizationMemberResponse,
    OrganizationResponse,
    OrganizationSwitchResponse,
    OrganizationUpdate,
)
from app.services.organization import OrganizationService

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.post("", response_model=OrganizationCreatedResponse, status_code=201)
async def create_organization(
    data: OrganizationCreate, current_user: CurrentUser, session: DBSession
):
    service = OrganizationService(session)
    return await service.create(data, current_user)


@router.get("", response_model=OrganizationListResponse)
async def list_organizations(
    current_user: CurrentUser,
    session: DBSession,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    service = OrganizationService(session)
    return await service.list_for_user(current_user, offset=offset, limit=limit)


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: str, current_user: CurrentUser, session: DBSession
):
    service = OrganizationService(session)
    return await service.get(organization_id, current_user)


@router.put("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: str,
    data: OrganizationUpdate,
    current_user: CurrentUser,
    session: DBSession,
):
    service = OrganizationService(session)
    return await service.update(organization_id, data, current_user)


@router.delete("/{organization_id}", status_code=204)
async def delete_organization(
    organization_id: str, current_user: CurrentUser, session: DBSession
):
    service = OrganizationService(session)
    await service.delete(organization_id, current_user)


@router.post("/{organization_id}/members", response_model=OrganizationMemberResponse, status_code=201)
async def add_organization_member(
    organization_id: str,
    data: OrganizationMemberCreate,
    current_user: CurrentUser,
    session: DBSession,
):
    service = OrganizationService(session)
    return await service.add_member(organization_id, data, current_user)


@router.get("/{organization_id}/members", response_model=OrganizationMemberListResponse)
async def list_organization_members(
    organization_id: str,
    current_user: CurrentUser,
    session: DBSession,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
):
    service = OrganizationService(session)
    return await service.list_members(
        organization_id, current_user, offset=offset, limit=limit
    )


@router.get("/{organization_id}/invitations", response_model=InvitationListResponse)
async def list_organization_invitations(
    organization_id: str,
    current_user: CurrentUser,
    session: DBSession,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
):
    service = OrganizationService(session)
    return await service.list_invitations(
        organization_id, current_user, offset=offset, limit=limit
    )


@router.delete("/{organization_id}/members/{member_id}", status_code=204)
async def remove_organization_member(
    organization_id: str,
    member_id: str,
    current_user: CurrentUser,
    session: DBSession,
):
    service = OrganizationService(session)
    await service.remove_member(organization_id, member_id, current_user)


@router.post("/{organization_id}/switch", response_model=OrganizationSwitchResponse)
async def switch_organization(
    organization_id: str, current_user: CurrentUser, session: DBSession
):
    service = OrganizationService(session)
    return await service.switch_organization(organization_id, current_user)
