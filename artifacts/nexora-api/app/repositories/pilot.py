"""Pilot readiness persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pilot import (
    PilotApproval,
    PilotAssessment,
    PilotChecklistItem,
    PilotEnrollment,
    PilotLiveOperation,
    PilotScorecard,
    PilotStage,
)
from app.repositories.base import BaseRepository


class PilotEnrollmentRepo(BaseRepository[PilotEnrollment]):
    def __init__(self, session: AsyncSession):
        super().__init__(PilotEnrollment, session)

    async def get_for_org(self, organization_id: str) -> PilotEnrollment | None:
        stmt = select(PilotEnrollment).where(PilotEnrollment.organization_id == organization_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()


class PilotChecklistRepo(BaseRepository[PilotChecklistItem]):
    def __init__(self, session: AsyncSession):
        super().__init__(PilotChecklistItem, session)

    async def list_for_enrollment(self, enrollment_id: str) -> list[PilotChecklistItem]:
        stmt = select(PilotChecklistItem).where(PilotChecklistItem.enrollment_id == enrollment_id)
        return list((await self.session.execute(stmt)).scalars().all())


class PilotAssessmentRepo(BaseRepository[PilotAssessment]):
    def __init__(self, session: AsyncSession):
        super().__init__(PilotAssessment, session)

    async def list_for_org(self, organization_id: str, *, limit: int = 20) -> list[PilotAssessment]:
        stmt = (
            select(PilotAssessment)
            .where(PilotAssessment.organization_id == organization_id)
            .order_by(PilotAssessment.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def latest(self, organization_id: str) -> PilotAssessment | None:
        rows = await self.list_for_org(organization_id, limit=1)
        return rows[0] if rows else None


class PilotScorecardRepo(BaseRepository[PilotScorecard]):
    def __init__(self, session: AsyncSession):
        super().__init__(PilotScorecard, session)

    async def latest(self, organization_id: str) -> PilotScorecard | None:
        stmt = (
            select(PilotScorecard)
            .where(PilotScorecard.organization_id == organization_id)
            .order_by(PilotScorecard.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class PilotLiveOperationRepo(BaseRepository[PilotLiveOperation]):
    def __init__(self, session: AsyncSession):
        super().__init__(PilotLiveOperation, session)

    async def list_for_org(self, organization_id: str, *, limit: int = 20) -> list[PilotLiveOperation]:
        stmt = (
            select(PilotLiveOperation)
            .where(PilotLiveOperation.organization_id == organization_id)
            .order_by(PilotLiveOperation.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_for_org(self, operation_id: str, organization_id: str) -> PilotLiveOperation | None:
        stmt = select(PilotLiveOperation).where(
            PilotLiveOperation.id == operation_id,
            PilotLiveOperation.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class PilotStageRepo(BaseRepository[PilotStage]):
    def __init__(self, session: AsyncSession):
        super().__init__(PilotStage, session)

    async def list_for_enrollment(self, enrollment_id: str) -> list[PilotStage]:
        stmt = select(PilotStage).where(PilotStage.enrollment_id == enrollment_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_stage(self, enrollment_id: str, stage_key: str) -> PilotStage | None:
        stmt = select(PilotStage).where(
            PilotStage.enrollment_id == enrollment_id,
            PilotStage.stage_key == stage_key,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class PilotApprovalRepo(BaseRepository[PilotApproval]):
    def __init__(self, session: AsyncSession):
        super().__init__(PilotApproval, session)

    async def get_for_org(self, approval_id: str, organization_id: str) -> PilotApproval | None:
        stmt = select(PilotApproval).where(
            PilotApproval.id == approval_id,
            PilotApproval.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
