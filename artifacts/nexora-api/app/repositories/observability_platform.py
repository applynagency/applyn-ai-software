"""Enterprise Observability Platform persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.observability_platform import (
    ObsAlertGroup,
    ObsCorrelationTimeline,
    ObsIntegration,
    ObsSavedSearch,
    ObsSLOEvaluation,
)
from app.repositories.base import BaseRepository


class ObsIntegrationRepo(BaseRepository[ObsIntegration]):
    def __init__(self, session: AsyncSession):
        super().__init__(ObsIntegration, session)

    async def list_active(self, organization_id: str, *, signal: str | None = None) -> list[ObsIntegration]:
        filters = [ObsIntegration.organization_id == organization_id, ObsIntegration.is_active.is_(True)]
        if signal:
            filters.append(ObsIntegration.signal == signal)
        stmt = select(ObsIntegration).where(*filters).order_by(ObsIntegration.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())


class ObsSavedSearchRepo(BaseRepository[ObsSavedSearch]):
    def __init__(self, session: AsyncSession):
        super().__init__(ObsSavedSearch, session)

    async def list_for_org(self, organization_id: str) -> list[ObsSavedSearch]:
        stmt = (
            select(ObsSavedSearch).where(ObsSavedSearch.organization_id == organization_id)
            .order_by(ObsSavedSearch.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class ObsCorrelationRepo(BaseRepository[ObsCorrelationTimeline]):
    def __init__(self, session: AsyncSession):
        super().__init__(ObsCorrelationTimeline, session)

    async def list_for_org(self, organization_id: str, *, limit: int = 50) -> list[ObsCorrelationTimeline]:
        stmt = (
            select(ObsCorrelationTimeline).where(ObsCorrelationTimeline.organization_id == organization_id)
            .order_by(ObsCorrelationTimeline.created_at.desc()).limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class ObsSLOEvalRepo(BaseRepository[ObsSLOEvaluation]):
    def __init__(self, session: AsyncSession):
        super().__init__(ObsSLOEvaluation, session)

    async def list_for_org(self, organization_id: str) -> list[ObsSLOEvaluation]:
        stmt = (
            select(ObsSLOEvaluation).where(ObsSLOEvaluation.organization_id == organization_id)
            .order_by(ObsSLOEvaluation.created_at.desc()).limit(100)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class ObsAlertGroupRepo(BaseRepository[ObsAlertGroup]):
    def __init__(self, session: AsyncSession):
        super().__init__(ObsAlertGroup, session)

    async def list_for_org(self, organization_id: str) -> list[ObsAlertGroup]:
        stmt = (
            select(ObsAlertGroup).where(ObsAlertGroup.organization_id == organization_id)
            .order_by(ObsAlertGroup.created_at.desc()).limit(50)
        )
        return list((await self.session.execute(stmt)).scalars().all())
