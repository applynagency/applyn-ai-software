"""Sprint 46A - data access for the Reliability Maturity Score Engine."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reliability_maturity import ReliabilityAssessment, ReliabilityScoreCategory
from app.repositories.base import BaseRepository


class ReliabilityAssessmentRepository(BaseRepository[ReliabilityAssessment]):
    def __init__(self, session: AsyncSession):
        super().__init__(ReliabilityAssessment, session)

    async def get_for_org(self, assessment_id: str, organization_id: str) -> ReliabilityAssessment | None:
        stmt = select(ReliabilityAssessment).where(
            ReliabilityAssessment.id == assessment_id,
            ReliabilityAssessment.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(
        self, organization_id: str, *, limit: int = 100
    ) -> list[ReliabilityAssessment]:
        stmt = (
            select(ReliabilityAssessment)
            .where(ReliabilityAssessment.organization_id == organization_id)
            .order_by(ReliabilityAssessment.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def latest(self, organization_id: str) -> ReliabilityAssessment | None:
        stmt = (
            select(ReliabilityAssessment)
            .where(ReliabilityAssessment.organization_id == organization_id)
            .order_by(ReliabilityAssessment.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class ReliabilityScoreCategoryRepository(BaseRepository[ReliabilityScoreCategory]):
    def __init__(self, session: AsyncSession):
        super().__init__(ReliabilityScoreCategory, session)

    async def list_for_assessment(
        self, assessment_id: str, organization_id: str
    ) -> list[ReliabilityScoreCategory]:
        stmt = (
            select(ReliabilityScoreCategory)
            .where(
                ReliabilityScoreCategory.assessment_id == assessment_id,
                ReliabilityScoreCategory.organization_id == organization_id,
            )
            .order_by(ReliabilityScoreCategory.weight.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())
