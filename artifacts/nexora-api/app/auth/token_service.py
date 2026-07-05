
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.models.organization import OrganizationRole
from app.repositories.organization import OrganizationMemberRepository
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse
from app.tenancy.backfill import ensure_user_has_organization


async def resolve_primary_org_claims(
    session: AsyncSession, user_id: str
) -> tuple[str | None, OrganizationRole | None]:
    member_repo = OrganizationMemberRepository(session)
    membership = await member_repo.get_primary_membership(user_id)
    if not membership:
        return None, None
    return membership.organization_id, membership.role


async def issue_tokens(
    session: AsyncSession,
    user_id: str,
    organization_id: str | None = None,
    role: OrganizationRole | None = None,
) -> TokenResponse:
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise ValueError("User not found")

    if organization_id is None or role is None:
        membership = await ensure_user_has_organization(session, user)
        organization_id = membership.organization_id
        role = membership.role

    extra = {}
    if organization_id and role:
        extra["organization_id"] = organization_id
        extra["role"] = role.value

    access_token = create_access_token(subject=user_id, extra=extra or None)
    refresh_extra = {}
    if organization_id:
        refresh_extra["organization_id"] = organization_id
    refresh_token = create_refresh_token(subject=user_id, extra=refresh_extra or None)

    await user_repo.update_refresh_token(user, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        organization_id=organization_id,
        role=role.value if role else None,
    )
