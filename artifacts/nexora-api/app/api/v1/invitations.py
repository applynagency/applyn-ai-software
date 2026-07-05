from fastapi import APIRouter

from app.auth.dependencies import CurrentUser, DBSession
from app.schemas.organization import (
    InvitationAccept,
    InvitationCreate,
    InvitationPreviewResponse,
    InvitationResponse,
    OrganizationMemberResponse,
)
from app.services.organization import OrganizationService

router = APIRouter(prefix="/invitations", tags=["Invitations"])


@router.post("", response_model=InvitationResponse, status_code=201)
async def create_invitation(
    data: InvitationCreate, current_user: CurrentUser, session: DBSession
):
    service = OrganizationService(session)
    return await service.create_invitation(data, current_user)


@router.get("/preview/{token}", response_model=InvitationPreviewResponse)
async def preview_invitation(token: str, session: DBSession):
    service = OrganizationService(session)
    return await service.preview_invitation(token)


@router.post("/accept", response_model=OrganizationMemberResponse)
async def accept_invitation(
    data: InvitationAccept, current_user: CurrentUser, session: DBSession
):
    service = OrganizationService(session)
    return await service.accept_invitation(data, current_user)


@router.post("/{invitation_id}/resend", response_model=InvitationResponse)
async def resend_invitation(
    invitation_id: str, current_user: CurrentUser, session: DBSession
):
    service = OrganizationService(session)
    return await service.resend_invitation(invitation_id, current_user)


@router.delete("/{invitation_id}", status_code=204)
async def revoke_invitation(
    invitation_id: str, current_user: CurrentUser, session: DBSession
):
    service = OrganizationService(session)
    await service.revoke_invitation(invitation_id, current_user)
