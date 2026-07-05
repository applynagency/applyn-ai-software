"""Data access for discovery scan runs (shared by Universal Discovery)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discovery_pipeline import DiscoveryScanRun
from app.repositories.base import BaseRepository


class DiscoveryScanRunRepository(BaseRepository[DiscoveryScanRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(DiscoveryScanRun, session)

    async def get_for_org(self, scan_id: str, organization_id: str) -> DiscoveryScanRun | None:
        stmt = select(DiscoveryScanRun).where(
            DiscoveryScanRun.id == scan_id,
            DiscoveryScanRun.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def latest_for_org(self, organization_id: str) -> DiscoveryScanRun | None:
        stmt = (
            select(DiscoveryScanRun)
            .where(DiscoveryScanRun.organization_id == organization_id)
            .order_by(DiscoveryScanRun.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(self, organization_id: str, *, limit: int = 50) -> list[DiscoveryScanRun]:
        stmt = (
            select(DiscoveryScanRun)
            .where(DiscoveryScanRun.organization_id == organization_id)
            .order_by(DiscoveryScanRun.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())
