from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cicd_agent import CicdArtifact, CicdRun
from app.repositories.base import BaseRepository


class CicdRunRepository(BaseRepository[CicdRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(CicdRun, session)

    async def get_with_artifact(self, run_id: str) -> CicdRun | None:
        stmt = (
            select(CicdRun)
            .where(CicdRun.id == run_id)
            .options(selectinload(CicdRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[CicdRun], int]:
        stmt = (
            select(CicdRun)
            .where(CicdRun.requirement_id == requirement_id)
            .options(selectinload(CicdRun.artifacts))
            .order_by(CicdRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(CicdRun).where(CicdRun.requirement_id == requirement_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[CicdRun], int]:
        stmt = (
            select(CicdRun)
            .where(CicdRun.organization_id == organization_id)
            .options(selectinload(CicdRun.artifacts))
            .order_by(CicdRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(CicdRun).where(CicdRun.organization_id == organization_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class CicdArtifactRepository(BaseRepository[CicdArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(CicdArtifact, session)

    async def get_for_org(self, artifact_id: str, organization_id: str) -> CicdArtifact | None:
        stmt = (
            select(CicdArtifact)
            .join(CicdRun, CicdArtifact.run_id == CicdRun.id)
            .where(
                CicdArtifact.id == artifact_id,
                CicdRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
