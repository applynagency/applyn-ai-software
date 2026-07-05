"""AI Platform Operator persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_operator import (
    OperatorActionProposal,
    OperatorExecutiveBriefing,
    OperatorGoal,
    OperatorLearningRecord,
    OperatorPolicy,
    OperatorRecommendation,
    OperatorSimulation,
    OperatorTimelineEntry,
)
from app.repositories.base import BaseRepository


class OperatorPolicyRepo(BaseRepository[OperatorPolicy]):
    def __init__(self, session: AsyncSession):
        super().__init__(OperatorPolicy, session)

    async def list_active(self, organization_id: str) -> list[OperatorPolicy]:
        stmt = (
            select(OperatorPolicy)
            .where(OperatorPolicy.organization_id == organization_id, OperatorPolicy.is_active.is_(True))
            .order_by(OperatorPolicy.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class OperatorGoalRepo(BaseRepository[OperatorGoal]):
    def __init__(self, session: AsyncSession):
        super().__init__(OperatorGoal, session)

    async def list_active(self, organization_id: str) -> list[OperatorGoal]:
        stmt = (
            select(OperatorGoal)
            .where(OperatorGoal.organization_id == organization_id, OperatorGoal.is_active.is_(True))
            .order_by(OperatorGoal.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class OperatorRecommendationRepo(BaseRepository[OperatorRecommendation]):
    def __init__(self, session: AsyncSession):
        super().__init__(OperatorRecommendation, session)

    async def list_for_org(self, organization_id: str, *, limit: int = 100) -> list[OperatorRecommendation]:
        stmt = (
            select(OperatorRecommendation)
            .where(OperatorRecommendation.organization_id == organization_id)
            .order_by(OperatorRecommendation.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_pending(self, organization_id: str) -> list[OperatorRecommendation]:
        stmt = (
            select(OperatorRecommendation)
            .where(
                OperatorRecommendation.organization_id == organization_id,
                OperatorRecommendation.status == "PENDING",
            )
            .order_by(OperatorRecommendation.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class OperatorSimulationRepo(BaseRepository[OperatorSimulation]):
    def __init__(self, session: AsyncSession):
        super().__init__(OperatorSimulation, session)

    async def list_for_org(self, organization_id: str) -> list[OperatorSimulation]:
        stmt = (
            select(OperatorSimulation)
            .where(OperatorSimulation.organization_id == organization_id)
            .order_by(OperatorSimulation.created_at.desc())
            .limit(50)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class OperatorProposalRepo(BaseRepository[OperatorActionProposal]):
    def __init__(self, session: AsyncSession):
        super().__init__(OperatorActionProposal, session)

    async def list_pending(self, organization_id: str) -> list[OperatorActionProposal]:
        stmt = (
            select(OperatorActionProposal)
            .where(
                OperatorActionProposal.organization_id == organization_id,
                OperatorActionProposal.status == "PENDING_APPROVAL",
            )
            .order_by(OperatorActionProposal.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class OperatorTimelineRepo(BaseRepository[OperatorTimelineEntry]):
    def __init__(self, session: AsyncSession):
        super().__init__(OperatorTimelineEntry, session)

    async def list_for_org(self, organization_id: str, *, limit: int = 100) -> list[OperatorTimelineEntry]:
        stmt = (
            select(OperatorTimelineEntry)
            .where(OperatorTimelineEntry.organization_id == organization_id)
            .order_by(OperatorTimelineEntry.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class OperatorLearningRepo(BaseRepository[OperatorLearningRecord]):
    def __init__(self, session: AsyncSession):
        super().__init__(OperatorLearningRecord, session)

    async def list_for_org(self, organization_id: str) -> list[OperatorLearningRecord]:
        stmt = (
            select(OperatorLearningRecord)
            .where(OperatorLearningRecord.organization_id == organization_id)
            .order_by(OperatorLearningRecord.created_at.desc())
            .limit(100)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class OperatorBriefingRepo(BaseRepository[OperatorExecutiveBriefing]):
    def __init__(self, session: AsyncSession):
        super().__init__(OperatorExecutiveBriefing, session)

    async def latest(self, organization_id: str) -> OperatorExecutiveBriefing | None:
        stmt = (
            select(OperatorExecutiveBriefing)
            .where(OperatorExecutiveBriefing.organization_id == organization_id)
            .order_by(OperatorExecutiveBriefing.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
