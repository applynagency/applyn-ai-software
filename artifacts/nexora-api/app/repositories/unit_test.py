from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.unit_test import UnitTestArtifact, UnitTestRun
from app.repositories.base import BaseRepository


class UnitTestRunRepository(BaseRepository[UnitTestRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(UnitTestRun, session)

    async def get_with_artifact(self, run_id: str) -> UnitTestRun | None:
        stmt = (
            select(UnitTestRun)
            .where(UnitTestRun.id == run_id)
            .options(selectinload(UnitTestRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[UnitTestRun], int]:
        stmt = (
            select(UnitTestRun)
            .where(UnitTestRun.requirement_id == requirement_id)
            .options(selectinload(UnitTestRun.artifacts))
            .order_by(UnitTestRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(UnitTestRun).where(UnitTestRun.requirement_id == requirement_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[UnitTestRun], int]:
        stmt = (
            select(UnitTestRun)
            .where(UnitTestRun.organization_id == organization_id)
            .options(selectinload(UnitTestRun.artifacts))
            .order_by(UnitTestRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(UnitTestRun).where(UnitTestRun.organization_id == organization_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class UnitTestArtifactRepository(BaseRepository[UnitTestArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(UnitTestArtifact, session)

    async def get_for_org(self, artifact_id: str, organization_id: str) -> UnitTestArtifact | None:
        stmt = (
            select(UnitTestArtifact)
            .join(UnitTestRun, UnitTestArtifact.run_id == UnitTestRun.id)
            .where(
                UnitTestArtifact.id == artifact_id,
                UnitTestRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
