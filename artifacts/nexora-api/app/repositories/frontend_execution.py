from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.frontend_execution import FrontendExecutionArtifact, FrontendExecutionRun
from app.repositories.base import BaseRepository


class FrontendExecutionRunRepository(BaseRepository[FrontendExecutionRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(FrontendExecutionRun, session)

    async def get_with_artifact(self, run_id: str) -> FrontendExecutionRun | None:
        stmt = (
            select(FrontendExecutionRun)
            .where(FrontendExecutionRun.id == run_id)
            .options(selectinload(FrontendExecutionRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[FrontendExecutionRun], int]:
        stmt = (
            select(FrontendExecutionRun)
            .where(FrontendExecutionRun.requirement_id == requirement_id)
            .options(selectinload(FrontendExecutionRun.artifacts))
            .order_by(FrontendExecutionRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(FrontendExecutionRun).where(
            FrontendExecutionRun.requirement_id == requirement_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[FrontendExecutionRun], int]:
        stmt = (
            select(FrontendExecutionRun)
            .where(FrontendExecutionRun.organization_id == organization_id)
            .options(selectinload(FrontendExecutionRun.artifacts))
            .order_by(FrontendExecutionRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(FrontendExecutionRun).where(
            FrontendExecutionRun.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class FrontendExecutionArtifactRepository(BaseRepository[FrontendExecutionArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(FrontendExecutionArtifact, session)

    async def get_for_org(
        self, artifact_id: str, organization_id: str
    ) -> FrontendExecutionArtifact | None:
        stmt = (
            select(FrontendExecutionArtifact)
            .join(FrontendExecutionRun, FrontendExecutionArtifact.run_id == FrontendExecutionRun.id)
            .where(
                FrontendExecutionArtifact.id == artifact_id,
                FrontendExecutionRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
