"""Sprint 47B - data access for the Integration Marketplace."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import IntegrationCatalog, IntegrationConnection
from app.repositories.base import BaseRepository


class IntegrationCatalogRepository(BaseRepository[IntegrationCatalog]):
    def __init__(self, session: AsyncSession):
        super().__init__(IntegrationCatalog, session)

    async def list_global(self) -> list[IntegrationCatalog]:
        stmt = (
            select(IntegrationCatalog)
            .where(IntegrationCatalog.organization_id.is_(None))
            .order_by(IntegrationCatalog.name.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_key(self, integration_key: str) -> IntegrationCatalog | None:
        stmt = (
            select(IntegrationCatalog)
            .where(
                IntegrationCatalog.organization_id.is_(None),
                IntegrationCatalog.integration_key == integration_key,
            )
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class IntegrationConnectionRepository(BaseRepository[IntegrationConnection]):
    def __init__(self, session: AsyncSession):
        super().__init__(IntegrationConnection, session)

    async def get_for_org(self, connection_id: str, organization_id: str) -> IntegrationConnection | None:
        stmt = select(IntegrationConnection).where(
            IntegrationConnection.id == connection_id,
            IntegrationConnection.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(self, organization_id: str) -> list[IntegrationConnection]:
        stmt = (
            select(IntegrationConnection)
            .where(IntegrationConnection.organization_id == organization_id)
            .order_by(IntegrationConnection.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())
