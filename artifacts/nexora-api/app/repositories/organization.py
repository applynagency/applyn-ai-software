import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import (
    InvitationStatus,
    Organization,
    OrganizationInvitation,
    OrganizationMember,
    OrganizationRole,
)
from app.repositories.base import BaseRepository


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-") or "org"


class OrganizationRepository(BaseRepository[Organization]):
    def __init__(self, session: AsyncSession):
        super().__init__(Organization, session)

    async def get_by_slug(self, slug: str) -> Organization | None:
        stmt = select(Organization).where(Organization.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: str, offset: int = 0, limit: int = 50
    ) -> tuple[list[Organization], int]:
        stmt = (
            select(Organization)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user_id)
            .offset(offset)
            .limit(limit)
        )
        count_stmt = (
            select(Organization)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().unique().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().unique().all()))
        return items, total

    async def list_memberships_for_user(
        self, user_id: str, offset: int = 0, limit: int = 50
    ) -> tuple[list[tuple[Organization, OrganizationRole]], int]:
        stmt = (
            select(Organization, OrganizationMember.role)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user_id)
            .order_by(Organization.name.asc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = (
            select(Organization.id)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        items = [(row[0], row[1]) for row in result.all()]
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class OrganizationMemberRepository(BaseRepository[OrganizationMember]):
    def __init__(self, session: AsyncSession):
        super().__init__(OrganizationMember, session)

    async def get_membership(
        self, organization_id: str, user_id: str
    ) -> OrganizationMember | None:
        stmt = select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: str, offset: int = 0, limit: int = 100
    ) -> tuple[list[OrganizationMember], int]:
        return await self.list_all(
            filters=[OrganizationMember.organization_id == organization_id],
            offset=offset,
            limit=limit,
        )

    async def get_primary_membership(self, user_id: str) -> OrganizationMember | None:
        stmt = (
            select(OrganizationMember)
            .where(OrganizationMember.user_id == user_id)
            .order_by(OrganizationMember.created_at.asc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_owners(self, organization_id: str) -> int:
        stmt = select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.role == OrganizationRole.OWNER,
        )
        result = await self.session.execute(stmt)
        return len(list(result.scalars().all()))


class OrganizationInvitationRepository(BaseRepository[OrganizationInvitation]):
    def __init__(self, session: AsyncSession):
        super().__init__(OrganizationInvitation, session)

    async def get_by_token(self, token: str) -> OrganizationInvitation | None:
        stmt = select(OrganizationInvitation).where(OrganizationInvitation.token == token)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pending_for_email(
        self, organization_id: str, email: str
    ) -> OrganizationInvitation | None:
        stmt = select(OrganizationInvitation).where(
            OrganizationInvitation.organization_id == organization_id,
            OrganizationInvitation.email == email.lower(),
            OrganizationInvitation.status == InvitationStatus.PENDING,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: str,
        *,
        status: InvitationStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[OrganizationInvitation], int]:
        filters = [OrganizationInvitation.organization_id == organization_id]
        if status is not None:
            filters.append(OrganizationInvitation.status == status)
        return await self.list_all(filters=filters, offset=offset, limit=limit)
