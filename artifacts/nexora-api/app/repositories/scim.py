"""Repositories for SCIM tokens, users, groups and group memberships."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scim import ScimGroup, ScimGroupMember, ScimToken, ScimUser
from app.repositories.base import BaseRepository


class ScimTokenRepository(BaseRepository[ScimToken]):
    def __init__(self, session: AsyncSession):
        super().__init__(ScimToken, session)

    async def get_by_hash(self, hashed_token: str) -> ScimToken | None:
        result = await self.session.execute(
            select(ScimToken).where(ScimToken.hashed_token == hashed_token)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(self, organization_id: str) -> list[ScimToken]:
        result = await self.session.execute(
            select(ScimToken)
            .where(ScimToken.organization_id == organization_id)
            .order_by(ScimToken.created_at.asc())
        )
        return list(result.scalars().all())


class ScimUserRepository(BaseRepository[ScimUser]):
    def __init__(self, session: AsyncSession):
        super().__init__(ScimUser, session)

    async def get_scoped(self, organization_id: str, scim_id: str) -> ScimUser | None:
        result = await self.session.execute(
            select(ScimUser).where(
                ScimUser.id == scim_id,
                ScimUser.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_username(
        self, organization_id: str, user_name: str
    ) -> ScimUser | None:
        result = await self.session.execute(
            select(ScimUser).where(
                ScimUser.organization_id == organization_id,
                ScimUser.user_name == user_name,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_external_id(
        self, organization_id: str, external_id: str
    ) -> ScimUser | None:
        result = await self.session.execute(
            select(ScimUser).where(
                ScimUser.organization_id == organization_id,
                ScimUser.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_filtered(
        self,
        organization_id: str,
        *,
        user_name: str | None = None,
        external_id: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[ScimUser], int]:
        filters = [ScimUser.organization_id == organization_id]
        if user_name is not None:
            filters.append(ScimUser.user_name == user_name)
        if external_id is not None:
            filters.append(ScimUser.external_id == external_id)
        return await self.list_all(filters=filters, offset=offset, limit=limit)


class ScimGroupRepository(BaseRepository[ScimGroup]):
    def __init__(self, session: AsyncSession):
        super().__init__(ScimGroup, session)

    async def get_scoped(self, organization_id: str, scim_id: str) -> ScimGroup | None:
        result = await self.session.execute(
            select(ScimGroup).where(
                ScimGroup.id == scim_id,
                ScimGroup.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_display_name(
        self, organization_id: str, display_name: str
    ) -> ScimGroup | None:
        result = await self.session.execute(
            select(ScimGroup).where(
                ScimGroup.organization_id == organization_id,
                ScimGroup.display_name == display_name,
            )
        )
        return result.scalar_one_or_none()

    async def list_filtered(
        self,
        organization_id: str,
        *,
        display_name: str | None = None,
        external_id: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[ScimGroup], int]:
        filters = [ScimGroup.organization_id == organization_id]
        if display_name is not None:
            filters.append(ScimGroup.display_name == display_name)
        if external_id is not None:
            filters.append(ScimGroup.external_id == external_id)
        return await self.list_all(filters=filters, offset=offset, limit=limit)


class ScimGroupMemberRepository(BaseRepository[ScimGroupMember]):
    def __init__(self, session: AsyncSession):
        super().__init__(ScimGroupMember, session)

    async def list_for_group(self, group_id: str) -> list[ScimGroupMember]:
        result = await self.session.execute(
            select(ScimGroupMember).where(ScimGroupMember.group_id == group_id)
        )
        return list(result.scalars().all())

    async def list_for_user(self, scim_user_id: str) -> list[ScimGroupMember]:
        result = await self.session.execute(
            select(ScimGroupMember).where(ScimGroupMember.scim_user_id == scim_user_id)
        )
        return list(result.scalars().all())

    async def get(self, group_id: str, scim_user_id: str) -> ScimGroupMember | None:
        result = await self.session.execute(
            select(ScimGroupMember).where(
                ScimGroupMember.group_id == group_id,
                ScimGroupMember.scim_user_id == scim_user_id,
            )
        )
        return result.scalar_one_or_none()
