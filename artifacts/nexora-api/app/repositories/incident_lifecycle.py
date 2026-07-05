"""Sprint 58A.4 — data access for incident lifecycle events, comments, tasks."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident_lifecycle import (
    IncidentComment,
    IncidentLifecycleEvent,
    IncidentTask,
)
from app.repositories.base import BaseRepository


class IncidentLifecycleEventRepository(BaseRepository[IncidentLifecycleEvent]):
    def __init__(self, session: AsyncSession):
        super().__init__(IncidentLifecycleEvent, session)

    async def list_for_incident(
        self, incident_id: str, organization_id: str, *, limit: int = 500
    ) -> list[IncidentLifecycleEvent]:
        stmt = (
            select(IncidentLifecycleEvent)
            .where(
                IncidentLifecycleEvent.incident_id == incident_id,
                IncidentLifecycleEvent.organization_id == organization_id,
            )
            .order_by(IncidentLifecycleEvent.created_at.asc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class IncidentCommentRepository(BaseRepository[IncidentComment]):
    def __init__(self, session: AsyncSession):
        super().__init__(IncidentComment, session)

    async def list_for_incident(
        self, incident_id: str, organization_id: str, *, limit: int = 500
    ) -> list[IncidentComment]:
        stmt = (
            select(IncidentComment)
            .where(
                IncidentComment.incident_id == incident_id,
                IncidentComment.organization_id == organization_id,
            )
            .order_by(IncidentComment.created_at.asc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class IncidentTaskRepository(BaseRepository[IncidentTask]):
    def __init__(self, session: AsyncSession):
        super().__init__(IncidentTask, session)

    async def get_for_org(self, task_id: str, organization_id: str) -> IncidentTask | None:
        stmt = select(IncidentTask).where(
            IncidentTask.id == task_id,
            IncidentTask.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_incident(
        self, incident_id: str, organization_id: str, *, limit: int = 500
    ) -> list[IncidentTask]:
        stmt = (
            select(IncidentTask)
            .where(
                IncidentTask.incident_id == incident_id,
                IncidentTask.organization_id == organization_id,
            )
            .order_by(IncidentTask.created_at.asc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())
