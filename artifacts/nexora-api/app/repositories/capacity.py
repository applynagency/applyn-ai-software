"""Sprint 43A — data access for capacity metrics & forecasts."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.capacity import CapacityForecast, CapacityMetric
from app.repositories.base import BaseRepository


class CapacityMetricRepository(BaseRepository[CapacityMetric]):
    def __init__(self, session: AsyncSession):
        super().__init__(CapacityMetric, session)

    async def add_many(self, rows: list[dict]) -> int:
        objs = [CapacityMetric(**r) for r in rows]
        self.session.add_all(objs)
        await self.session.flush()
        return len(objs)

    async def query(
        self,
        organization_id: str,
        *,
        resource_type: str | None = None,
        cluster: str | None = None,
        service: str | None = None,
        environment: str | None = None,
        since: datetime | None = None,
    ) -> list[CapacityMetric]:
        filters = [CapacityMetric.organization_id == organization_id]
        if resource_type:
            filters.append(CapacityMetric.resource_type == resource_type)
        if cluster:
            filters.append(CapacityMetric.cluster == cluster)
        if service:
            filters.append(CapacityMetric.service == service)
        if environment:
            filters.append(CapacityMetric.environment == environment)
        if since is not None:
            filters.append(CapacityMetric.recorded_at >= since)
        stmt = select(CapacityMetric).where(*filters).order_by(CapacityMetric.recorded_at.asc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def distinct_resource_types(
        self, organization_id: str, *, cluster=None, service=None, environment=None
    ) -> list[str]:
        filters = [CapacityMetric.organization_id == organization_id]
        if cluster:
            filters.append(CapacityMetric.cluster == cluster)
        if service:
            filters.append(CapacityMetric.service == service)
        if environment:
            filters.append(CapacityMetric.environment == environment)
        stmt = select(CapacityMetric.resource_type).where(*filters).distinct()
        return list((await self.session.execute(stmt)).scalars().all())


class CapacityForecastRepository(BaseRepository[CapacityForecast]):
    def __init__(self, session: AsyncSession):
        super().__init__(CapacityForecast, session)

    async def get_for_org(self, forecast_id: str, organization_id: str) -> CapacityForecast | None:
        stmt = select(CapacityForecast).where(
            CapacityForecast.id == forecast_id,
            CapacityForecast.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[CapacityForecast], int]:
        base = select(CapacityForecast).where(CapacityForecast.organization_id == organization_id)
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            await self.session.execute(
                base.order_by(CapacityForecast.created_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)

    async def list_recent(self, organization_id: str, *, limit: int = 200) -> list[CapacityForecast]:
        stmt = (
            select(CapacityForecast)
            .where(CapacityForecast.organization_id == organization_id)
            .order_by(CapacityForecast.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())
