"""Repositories for SSO connections and external identities."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sso import SSOConnection, SSOIdentity
from app.repositories.base import BaseRepository


class SSOConnectionRepository(BaseRepository[SSOConnection]):
    def __init__(self, session: AsyncSession):
        super().__init__(SSOConnection, session)

    async def get_by_slug(self, slug: str) -> SSOConnection | None:
        result = await self.session.execute(
            select(SSOConnection).where(SSOConnection.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_enabled(self) -> list[SSOConnection]:
        result = await self.session.execute(
            select(SSOConnection)
            .where(SSOConnection.enabled.is_(True))
            .order_by(SSOConnection.display_name.asc())
        )
        return list(result.scalars().all())

    async def list_for_organization(
        self, organization_id: str | None
    ) -> list[SSOConnection]:
        stmt = select(SSOConnection)
        if organization_id is not None:
            stmt = stmt.where(SSOConnection.organization_id == organization_id)
        result = await self.session.execute(stmt.order_by(SSOConnection.created_at.asc()))
        return list(result.scalars().all())


class SSOIdentityRepository(BaseRepository[SSOIdentity]):
    def __init__(self, session: AsyncSession):
        super().__init__(SSOIdentity, session)

    async def get_by_subject(
        self, connection_id: str, external_subject: str
    ) -> SSOIdentity | None:
        result = await self.session.execute(
            select(SSOIdentity).where(
                SSOIdentity.connection_id == connection_id,
                SSOIdentity.external_subject == external_subject,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: str) -> list[SSOIdentity]:
        result = await self.session.execute(
            select(SSOIdentity).where(SSOIdentity.user_id == user_id)
        )
        return list(result.scalars().all())
