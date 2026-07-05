from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.performance_test import PerformanceTestArtifact, PerformanceTestRun
from app.repositories.base import BaseRepository


class PerformanceTestRunRepository(BaseRepository[PerformanceTestRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(PerformanceTestRun, session)

    async def get_with_artifact(self, run_id: str) -> PerformanceTestRun | None:
        stmt = (
            select(PerformanceTestRun)
            .where(PerformanceTestRun.id == run_id)
            .options(selectinload(PerformanceTestRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[PerformanceTestRun], int]:
        stmt = (
            select(PerformanceTestRun)
            .where(PerformanceTestRun.requirement_id == requirement_id)
            .options(selectinload(PerformanceTestRun.artifacts))
            .order_by(PerformanceTestRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(PerformanceTestRun).where(PerformanceTestRun.requirement_id == requirement_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[PerformanceTestRun], int]:
        stmt = (
            select(PerformanceTestRun)
            .where(PerformanceTestRun.organization_id == organization_id)
            .options(selectinload(PerformanceTestRun.artifacts))
            .order_by(PerformanceTestRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(PerformanceTestRun).where(
            PerformanceTestRun.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class PerformanceTestArtifactRepository(BaseRepository[PerformanceTestArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(PerformanceTestArtifact, session)

    async def get_for_org(
        self, artifact_id: str, organization_id: str
    ) -> PerformanceTestArtifact | None:
        stmt = (
            select(PerformanceTestArtifact)
            .join(PerformanceTestRun, PerformanceTestArtifact.run_id == PerformanceTestRun.id)
            .where(
                PerformanceTestArtifact.id == artifact_id,
                PerformanceTestRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
