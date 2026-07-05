from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.backend_architect import BackendArchitectArtifact, BackendArchitectRun
from app.repositories.base import BaseRepository


class BackendArchitectRunRepository(BaseRepository[BackendArchitectRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(BackendArchitectRun, session)

    async def get_with_artifact(self, run_id: str) -> BackendArchitectRun | None:
        stmt = (
            select(BackendArchitectRun)
            .where(BackendArchitectRun.id == run_id)
            .options(selectinload(BackendArchitectRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[BackendArchitectRun], int]:
        stmt = (
            select(BackendArchitectRun)
            .where(BackendArchitectRun.requirement_id == requirement_id)
            .options(selectinload(BackendArchitectRun.artifacts))
            .order_by(BackendArchitectRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(BackendArchitectRun).where(
            BackendArchitectRun.requirement_id == requirement_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[BackendArchitectRun], int]:
        stmt = (
            select(BackendArchitectRun)
            .where(BackendArchitectRun.organization_id == organization_id)
            .options(selectinload(BackendArchitectRun.artifacts))
            .order_by(BackendArchitectRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(BackendArchitectRun).where(
            BackendArchitectRun.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class BackendArchitectArtifactRepository(BaseRepository[BackendArchitectArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(BackendArchitectArtifact, session)

    async def get_for_org(self, artifact_id: str, organization_id: str) -> BackendArchitectArtifact | None:
        stmt = (
            select(BackendArchitectArtifact)
            .join(BackendArchitectRun, BackendArchitectArtifact.run_id == BackendArchitectRun.id)
            .where(
                BackendArchitectArtifact.id == artifact_id,
                BackendArchitectRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_run_for_org(self, run_id: str, organization_id: str) -> BackendArchitectRun | None:
        stmt = select(BackendArchitectRun).where(
            BackendArchitectRun.id == run_id,
            BackendArchitectRun.organization_id == organization_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
