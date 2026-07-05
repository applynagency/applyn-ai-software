"""Sprint 43B — data access for cost-optimization analyses."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cost_optimization import CostOptimizationAnalysis
from app.repositories.base import BaseRepository


class CostOptimizationRepository(BaseRepository[CostOptimizationAnalysis]):
    def __init__(self, session: AsyncSession):
        super().__init__(CostOptimizationAnalysis, session)

    async def get_for_org(self, analysis_id: str, organization_id: str) -> CostOptimizationAnalysis | None:
        stmt = select(CostOptimizationAnalysis).where(
            CostOptimizationAnalysis.id == analysis_id,
            CostOptimizationAnalysis.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[CostOptimizationAnalysis], int]:
        base = select(CostOptimizationAnalysis).where(
            CostOptimizationAnalysis.organization_id == organization_id
        )
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            await self.session.execute(
                base.order_by(CostOptimizationAnalysis.created_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)

    async def latest(self, organization_id: str) -> CostOptimizationAnalysis | None:
        stmt = (
            select(CostOptimizationAnalysis)
            .where(CostOptimizationAnalysis.organization_id == organization_id)
            .order_by(CostOptimizationAnalysis.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
