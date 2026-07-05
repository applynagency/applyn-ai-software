"""Sprint 44A — data access for incident postmortems."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.postmortem import IncidentPostmortem
from app.repositories.base import BaseRepository


class PostmortemRepository(BaseRepository[IncidentPostmortem]):
    def __init__(self, session: AsyncSession):
        super().__init__(IncidentPostmortem, session)

    async def get_for_org(self, postmortem_id: str, organization_id: str) -> IncidentPostmortem | None:
        stmt = select(IncidentPostmortem).where(
            IncidentPostmortem.id == postmortem_id,
            IncidentPostmortem.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_for_investigation(
        self, investigation_id: str, organization_id: str
    ) -> IncidentPostmortem | None:
        stmt = select(IncidentPostmortem).where(
            IncidentPostmortem.investigation_id == investigation_id,
            IncidentPostmortem.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[IncidentPostmortem], int]:
        base = select(IncidentPostmortem).where(
            IncidentPostmortem.organization_id == organization_id
        )
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            await self.session.execute(
                base.order_by(IncidentPostmortem.created_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)
