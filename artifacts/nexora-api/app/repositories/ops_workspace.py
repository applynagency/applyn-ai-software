"""DevOps & SRE workspace persistence layer."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ops_workspace import (
    WorkspaceAutomationSuggestion,
    WorkspaceCalendarEvent,
    WorkspaceDailyBriefing,
    WorkspaceMaintenanceWindow,
    WorkspaceShiftHandover,
)
from app.repositories.base import BaseRepository


class OpsMaintenanceRepository(BaseRepository[WorkspaceMaintenanceWindow]):
    def __init__(self, session: AsyncSession):
        super().__init__(WorkspaceMaintenanceWindow, session)

    async def list_for_org(self, organization_id: str) -> list[WorkspaceMaintenanceWindow]:
        stmt = (
            select(WorkspaceMaintenanceWindow)
            .where(WorkspaceMaintenanceWindow.organization_id == organization_id)
            .order_by(WorkspaceMaintenanceWindow.starts_at.desc())
            .limit(100)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class OpsBriefingRepository(BaseRepository[WorkspaceDailyBriefing]):
    def __init__(self, session: AsyncSession):
        super().__init__(WorkspaceDailyBriefing, session)

    async def latest(self, organization_id: str) -> WorkspaceDailyBriefing | None:
        stmt = (
            select(WorkspaceDailyBriefing)
            .where(WorkspaceDailyBriefing.organization_id == organization_id)
            .order_by(WorkspaceDailyBriefing.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class OpsHandoverRepository(BaseRepository[WorkspaceShiftHandover]):
    def __init__(self, session: AsyncSession):
        super().__init__(WorkspaceShiftHandover, session)

    async def latest(self, organization_id: str) -> WorkspaceShiftHandover | None:
        stmt = (
            select(WorkspaceShiftHandover)
            .where(WorkspaceShiftHandover.organization_id == organization_id)
            .order_by(WorkspaceShiftHandover.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class OpsAutomationRepository(BaseRepository[WorkspaceAutomationSuggestion]):
    def __init__(self, session: AsyncSession):
        super().__init__(WorkspaceAutomationSuggestion, session)

    async def list_active(self, organization_id: str) -> list[WorkspaceAutomationSuggestion]:
        stmt = (
            select(WorkspaceAutomationSuggestion)
            .where(
                WorkspaceAutomationSuggestion.organization_id == organization_id,
                WorkspaceAutomationSuggestion.dismissed.is_(False),
            )
            .order_by(WorkspaceAutomationSuggestion.occurrence_count.desc())
            .limit(50)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class OpsCalendarRepository(BaseRepository[WorkspaceCalendarEvent]):
    def __init__(self, session: AsyncSession):
        super().__init__(WorkspaceCalendarEvent, session)

    async def list_for_org(self, organization_id: str) -> list[WorkspaceCalendarEvent]:
        stmt = (
            select(WorkspaceCalendarEvent)
            .where(WorkspaceCalendarEvent.organization_id == organization_id)
            .order_by(WorkspaceCalendarEvent.starts_at.asc())
            .limit(200)
        )
        return list((await self.session.execute(stmt)).scalars().all())
