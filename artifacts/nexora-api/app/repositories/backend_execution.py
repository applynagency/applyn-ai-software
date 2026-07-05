from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.backend_execution import BackendExecutionArtifact, BackendExecutionRun
from app.repositories.base import BaseRepository


class BackendExecutionRunRepository(BaseRepository[BackendExecutionRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(BackendExecutionRun, session)

    async def get_with_artifact(self, run_id: str) -> BackendExecutionRun | None:
        stmt = (
            select(BackendExecutionRun)
            .where(BackendExecutionRun.id == run_id)
            .options(selectinload(BackendExecutionRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[BackendExecutionRun], int]:
        stmt = (
            select(BackendExecutionRun)
            .where(BackendExecutionRun.requirement_id == requirement_id)
            .options(selectinload(BackendExecutionRun.artifacts))
            .order_by(BackendExecutionRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(BackendExecutionRun).where(
            BackendExecutionRun.requirement_id == requirement_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[BackendExecutionRun], int]:
        stmt = (
            select(BackendExecutionRun)
            .where(BackendExecutionRun.organization_id == organization_id)
            .options(selectinload(BackendExecutionRun.artifacts))
            .order_by(BackendExecutionRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(BackendExecutionRun).where(
            BackendExecutionRun.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class BackendExecutionArtifactRepository(BaseRepository[BackendExecutionArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(BackendExecutionArtifact, session)

    async def get_for_org(
        self, artifact_id: str, organization_id: str
    ) -> BackendExecutionArtifact | None:
        stmt = (
            select(BackendExecutionArtifact)
            .join(BackendExecutionRun, BackendExecutionArtifact.run_id == BackendExecutionRun.id)
            .where(
                BackendExecutionArtifact.id == artifact_id,
                BackendExecutionRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
