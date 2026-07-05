from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.fullstack_assembly import FullstackAssemblyArtifact, FullstackAssemblyRun
from app.repositories.base import BaseRepository


class FullstackAssemblyRunRepository(BaseRepository[FullstackAssemblyRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(FullstackAssemblyRun, session)

    async def get_with_artifact(self, run_id: str) -> FullstackAssemblyRun | None:
        stmt = (
            select(FullstackAssemblyRun)
            .where(FullstackAssemblyRun.id == run_id)
            .options(selectinload(FullstackAssemblyRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[FullstackAssemblyRun], int]:
        stmt = (
            select(FullstackAssemblyRun)
            .where(FullstackAssemblyRun.requirement_id == requirement_id)
            .options(selectinload(FullstackAssemblyRun.artifacts))
            .order_by(FullstackAssemblyRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(FullstackAssemblyRun).where(
            FullstackAssemblyRun.requirement_id == requirement_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[FullstackAssemblyRun], int]:
        stmt = (
            select(FullstackAssemblyRun)
            .where(FullstackAssemblyRun.organization_id == organization_id)
            .options(selectinload(FullstackAssemblyRun.artifacts))
            .order_by(FullstackAssemblyRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(FullstackAssemblyRun).where(
            FullstackAssemblyRun.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class FullstackAssemblyArtifactRepository(BaseRepository[FullstackAssemblyArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(FullstackAssemblyArtifact, session)

    async def get_for_org(
        self, artifact_id: str, organization_id: str
    ) -> FullstackAssemblyArtifact | None:
        stmt = (
            select(FullstackAssemblyArtifact)
            .join(
                FullstackAssemblyRun,
                FullstackAssemblyArtifact.run_id == FullstackAssemblyRun.id,
            )
            .where(
                FullstackAssemblyArtifact.id == artifact_id,
                FullstackAssemblyRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
