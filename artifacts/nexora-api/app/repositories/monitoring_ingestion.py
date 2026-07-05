"""Sprint 58A.3 — data access for the monitoring ingestion dead-letter queue."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monitoring_ingestion import MonitoringDeadLetter
from app.repositories.base import BaseRepository


class MonitoringDeadLetterRepository(BaseRepository[MonitoringDeadLetter]):
    def __init__(self, session: AsyncSession):
        super().__init__(MonitoringDeadLetter, session)

    async def list_for_org(
        self, organization_id: str, *, status: str | None = None, limit: int = 100
    ) -> list[MonitoringDeadLetter]:
        stmt = select(MonitoringDeadLetter).where(
            MonitoringDeadLetter.organization_id == organization_id
        )
        if status:
            stmt = stmt.where(MonitoringDeadLetter.status == status)
        stmt = stmt.order_by(MonitoringDeadLetter.created_at.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def count_pending(self, organization_id: str) -> int:
        from sqlalchemy import func

        from app.models.monitoring_ingestion import DeadLetterStatus

        stmt = select(func.count()).select_from(MonitoringDeadLetter).where(
            MonitoringDeadLetter.organization_id == organization_id,
            MonitoringDeadLetter.status == DeadLetterStatus.PENDING.value,
        )
        return int((await self.session.execute(stmt)).scalar_one())
