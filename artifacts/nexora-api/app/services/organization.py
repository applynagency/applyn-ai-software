from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.token_service import issue_tokens
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.organization import (
    InvitationStatus,
    OrganizationInvitation,
    OrganizationRole,
)
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.organization import (
    OrganizationInvitationRepository,
    OrganizationMemberRepository,
    OrganizationRepository,
    slugify,
)
from app.repositories.user import UserRepository
from app.schemas.organization import (
    InvitationAccept,
    InvitationCreate,
    InvitationListResponse,
    InvitationPreviewResponse,
    InvitationResponse,
    OrganizationContextToken,
    OrganizationCreate,
    OrganizationCreatedResponse,
    OrganizationListItemResponse,
    OrganizationListResponse,
    OrganizationMemberCreate,
    OrganizationMemberListResponse,
    OrganizationMemberResponse,
    OrganizationResponse,
    OrganizationSwitchResponse,
    OrganizationUpdate,
)
from app.tenancy.permissions import can_assign_role, can_manage_members, can_manage_organization

logger = get_logger(__name__)


class OrganizationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.org_repo = OrganizationRepository(session)
        self.member_repo = OrganizationMemberRepository(session)
        self.invitation_repo = OrganizationInvitationRepository(session)
        self.user_repo = UserRepository(session)
        self.audit_repo = AuditLogRepository(session)

    async def _get_membership(self, organization_id: str, user: User):
        membership = await self.member_repo.get_membership(organization_id, user.id)
        if not membership and not user.is_superuser:
            raise NotFoundError("Organization", organization_id)
        return membership

    def _ensure_can_assign_role(self, membership, target_role: OrganizationRole) -> None:
        if membership and not can_assign_role(membership.role, target_role):
            raise ForbiddenError("Only owners can assign the owner role")

    async def create(
        self, data: OrganizationCreate, current_user: User
    ) -> OrganizationCreatedResponse:
        slug = data.slug or slugify(data.name)
        existing = await self.org_repo.get_by_slug(slug)
        if existing:
            raise ConflictError(f"Organization slug '{slug}' is already taken")

        organization = await self.org_repo.create(
            name=data.name,
            slug=slug,
            description=data.description,
        )
        await self.member_repo.create(
            organization_id=organization.id,
            user_id=current_user.id,
            role=OrganizationRole.OWNER,
        )
        await self.audit_repo.log(
            action="organization.create",
            resource_type="organization",
            resource_id=organization.id,
            user_id=current_user.id,
        )
        logger.info("organization_created", organization_id=organization.id)

        # Sprint 62A: emit a first-class domain event (feeds the activity feed,
        # notifications and any subscribed integrations). Best-effort.
        from app.platform.events import DomainEventType, emit_event

        await emit_event(
            self.session, DomainEventType.ORGANIZATION_CREATED,
            organization_id=organization.id, actor_id=current_user.id,
            aggregate_type="organization", aggregate_id=organization.id,
            payload={"summary": f"Organization '{organization.name}' created",
                     "name": organization.name}, source="organization")

        # Sprint 54B.1 — auto-switch into the org the user just created and hand
        # back org-scoped tokens, so no manual /switch call is required before
        # using org-scoped endpoints (removes the post-create 403 dead-end).
        response = OrganizationCreatedResponse.model_validate(organization)
        tokens = await issue_tokens(
            self.session,
            current_user.id,
            organization_id=organization.id,
            role=OrganizationRole.OWNER,
        )
        response.auto_switched = True
        response.context = OrganizationContextToken(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_in=tokens.expires_in,
            organization_id=organization.id,
            role=OrganizationRole.OWNER,
        )
        return response

    async def list_for_user(
        self, current_user: User, offset: int = 0, limit: int = 50
    ) -> OrganizationListResponse:
        rows, total = await self.org_repo.list_memberships_for_user(
            current_user.id, offset, limit
        )
        items = [
            OrganizationListItemResponse(
                **OrganizationResponse.model_validate(org).model_dump(),
                role=role,
            )
            for org, role in rows
        ]
        return OrganizationListResponse(items=items, total=total)

    async def get(self, organization_id: str, current_user: User) -> OrganizationResponse:
        organization = await self.org_repo.get_by_id(organization_id)
        if not organization:
            raise NotFoundError("Organization", organization_id)
        await self._get_membership(organization_id, current_user)
        return OrganizationResponse.model_validate(organization)

    async def update(
        self, organization_id: str, data: OrganizationUpdate, current_user: User
    ) -> OrganizationResponse:
        organization = await self.org_repo.get_by_id(organization_id)
        if not organization:
            raise NotFoundError("Organization", organization_id)
        membership = await self._get_membership(organization_id, current_user)
        if membership and not can_manage_organization(membership.role):
            raise ForbiddenError("Only owners and admins can update organizations")

        updated = await self.org_repo.update(
            organization, **data.model_dump(exclude_none=True)
        )
        await self.audit_repo.log(
            action="organization.update",
            resource_type="organization",
            resource_id=organization_id,
            user_id=current_user.id,
        )
        return OrganizationResponse.model_validate(updated)

    async def delete(self, organization_id: str, current_user: User) -> None:
        organization = await self.org_repo.get_by_id(organization_id)
        if not organization:
            raise NotFoundError("Organization", organization_id)
        membership = await self._get_membership(organization_id, current_user)
        if membership and membership.role != OrganizationRole.OWNER:
            raise ForbiddenError("Only owners can delete organizations")

        await self.org_repo.hard_delete(organization)
        await self.audit_repo.log(
            action="organization.delete",
            resource_type="organization",
            resource_id=organization_id,
            user_id=current_user.id,
        )

    async def add_member(
        self, organization_id: str, data: OrganizationMemberCreate, current_user: User
    ) -> OrganizationMemberResponse:
        organization = await self.org_repo.get_by_id(organization_id)
        if not organization:
            raise NotFoundError("Organization", organization_id)
        membership = await self._get_membership(organization_id, current_user)
        if membership and not can_manage_members(membership.role):
            raise ForbiddenError("Only owners and admins can manage members")

        user = await self.user_repo.get_by_id(data.user_id)
        if not user:
            raise NotFoundError("User", data.user_id)

        existing = await self.member_repo.get_membership(organization_id, data.user_id)
        if existing:
            raise ConflictError("User is already a member of this organization")

        self._ensure_can_assign_role(membership, data.role)

        member = await self.member_repo.create(
            organization_id=organization_id,
            user_id=data.user_id,
            role=data.role,
        )
        return OrganizationMemberResponse.model_validate(member)

    async def list_members(
        self, organization_id: str, current_user: User, offset: int = 0, limit: int = 100
    ) -> OrganizationMemberListResponse:
        organization = await self.org_repo.get_by_id(organization_id)
        if not organization:
            raise NotFoundError("Organization", organization_id)
        await self._get_membership(organization_id, current_user)
        items, total = await self.member_repo.list_for_organization(
            organization_id, offset=offset, limit=limit
        )
        return OrganizationMemberListResponse(
            items=[OrganizationMemberResponse.model_validate(item) for item in items],
            total=total,
        )

    async def remove_member(
        self, organization_id: str, member_id: str, current_user: User
    ) -> None:
        organization = await self.org_repo.get_by_id(organization_id)
        if not organization:
            raise NotFoundError("Organization", organization_id)
        actor_membership = await self._get_membership(organization_id, current_user)
        if actor_membership and not can_manage_members(actor_membership.role):
            raise ForbiddenError("Only owners and admins can manage members")

        member = await self.member_repo.get_by_id(member_id)
        if not member or member.organization_id != organization_id:
            raise NotFoundError("OrganizationMember", member_id)

        if member.role == OrganizationRole.OWNER:
            owner_count = await self.member_repo.count_owners(organization_id)
            if owner_count <= 1:
                raise ValidationError("Cannot remove the last organization owner")

        await self.member_repo.hard_delete(member)

    async def switch_organization(
        self, organization_id: str, current_user: User
    ) -> OrganizationSwitchResponse:
        organization = await self.org_repo.get_by_id(organization_id)
        if not organization:
            raise NotFoundError("Organization", organization_id)
        membership = await self.member_repo.get_membership(organization_id, current_user.id)
        if not membership and not current_user.is_superuser:
            raise NotFoundError("Organization", organization_id)

        role = membership.role if membership else OrganizationRole.OWNER
        tokens = await issue_tokens(
            self.session,
            current_user.id,
            organization_id=organization_id,
            role=role,
        )
        return OrganizationSwitchResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_in=tokens.expires_in,
            organization_id=organization_id,
            role=role,
        )

    async def create_invitation(
        self, data: InvitationCreate, current_user: User
    ) -> InvitationResponse:
        organization = await self.org_repo.get_by_id(data.organization_id)
        if not organization:
            raise NotFoundError("Organization", data.organization_id)
        membership = await self._get_membership(data.organization_id, current_user)
        if membership and not can_manage_members(membership.role):
            raise ForbiddenError("Only owners and admins can invite members")

        email = data.email.lower()
        existing_user = await self.user_repo.get_by_email(email)
        if existing_user:
            existing_member = await self.member_repo.get_membership(
                data.organization_id, existing_user.id
            )
            if existing_member:
                raise ConflictError("User is already a member of this organization")

        pending = await self.invitation_repo.get_pending_for_email(data.organization_id, email)
        if pending:
            raise ConflictError("A pending invitation already exists for this email")

        self._ensure_can_assign_role(membership, data.role)

        invitation = await self.invitation_repo.create(
            organization_id=data.organization_id,
            email=email,
            role=data.role,
            token=OrganizationInvitation.generate_token(),
            invited_by=current_user.id,
            status=InvitationStatus.PENDING,
            expires_at=OrganizationInvitation.default_expiry(),
        )
        return InvitationResponse.model_validate(invitation)

    async def accept_invitation(
        self, data: InvitationAccept, current_user: User
    ) -> OrganizationMemberResponse:
        invitation = await self.invitation_repo.get_by_token(data.token)
        if not invitation or not invitation.is_valid():
            raise ValidationError("Invitation is invalid or expired")

        if invitation.email.lower() != current_user.email.lower():
            raise ForbiddenError("Invitation email does not match your account")

        existing = await self.member_repo.get_membership(
            invitation.organization_id, current_user.id
        )
        if existing:
            raise ConflictError("You are already a member of this organization")

        member = await self.member_repo.create(
            organization_id=invitation.organization_id,
            user_id=current_user.id,
            role=invitation.role,
        )
        await self.invitation_repo.update(invitation, status=InvitationStatus.ACCEPTED)
        return OrganizationMemberResponse.model_validate(member)

    async def list_invitations(
        self, organization_id: str, current_user: User, offset: int = 0, limit: int = 100
    ) -> InvitationListResponse:
        organization = await self.org_repo.get_by_id(organization_id)
        if not organization:
            raise NotFoundError("Organization", organization_id)
        membership = await self._get_membership(organization_id, current_user)
        if membership and not can_manage_members(membership.role):
            raise ForbiddenError("Only owners and admins can view invitations")

        items, total = await self.invitation_repo.list_for_organization(
            organization_id,
            status=InvitationStatus.PENDING,
            offset=offset,
            limit=limit,
        )
        return InvitationListResponse(
            items=[InvitationResponse.model_validate(item) for item in items],
            total=total,
        )

    async def preview_invitation(self, token: str) -> InvitationPreviewResponse:
        invitation = await self.invitation_repo.get_by_token(token)
        organization = (
            await self.org_repo.get_by_id(invitation.organization_id)
            if invitation
            else None
        )
        if not invitation or not organization:
            return InvitationPreviewResponse(
                organization_name="",
                email="",
                role=OrganizationRole.DEVELOPER,
                valid=False,
            )
        return InvitationPreviewResponse(
            organization_name=organization.name,
            email=invitation.email,
            role=invitation.role,
            valid=invitation.is_valid(),
        )

    async def resend_invitation(
        self, invitation_id: str, current_user: User
    ) -> InvitationResponse:
        invitation = await self.invitation_repo.get_by_id(invitation_id)
        if not invitation:
            raise NotFoundError("Invitation", invitation_id)
        membership = await self._get_membership(invitation.organization_id, current_user)
        if membership and not can_manage_members(membership.role):
            raise ForbiddenError("Only owners and admins can resend invitations")
        if invitation.status != InvitationStatus.PENDING:
            raise ValidationError("Only pending invitations can be resent")

        updated = await self.invitation_repo.update(
            invitation,
            token=OrganizationInvitation.generate_token(),
            expires_at=OrganizationInvitation.default_expiry(),
        )
        return InvitationResponse.model_validate(updated)

    async def revoke_invitation(self, invitation_id: str, current_user: User) -> None:
        invitation = await self.invitation_repo.get_by_id(invitation_id)
        if not invitation:
            raise NotFoundError("Invitation", invitation_id)
        membership = await self._get_membership(invitation.organization_id, current_user)
        if membership and not can_manage_members(membership.role):
            raise ForbiddenError("Only owners and admins can revoke invitations")
        if invitation.status != InvitationStatus.PENDING:
            raise ValidationError("Only pending invitations can be revoked")

        await self.invitation_repo.update(invitation, status=InvitationStatus.REVOKED)
