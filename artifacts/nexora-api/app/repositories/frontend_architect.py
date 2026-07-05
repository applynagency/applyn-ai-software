from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.frontend_architect import FrontendArchitectArtifact, FrontendArchitectRun
from app.repositories.base import BaseRepository


class FrontendArchitectRunRepository(BaseRepository[FrontendArchitectRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(FrontendArchitectRun, session)

    async def get_with_artifact(self, run_id: str) -> FrontendArchitectRun | None:
        stmt = (
            select(FrontendArchitectRun)
            .where(FrontendArchitectRun.id == run_id)
            .options(selectinload(FrontendArchitectRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[FrontendArchitectRun], int]:
        stmt = (
            select(FrontendArchitectRun)
            .where(FrontendArchitectRun.requirement_id == requirement_id)
            .options(selectinload(FrontendArchitectRun.artifacts))
            .order_by(FrontendArchitectRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(FrontendArchitectRun).where(
            FrontendArchitectRun.requirement_id == requirement_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[FrontendArchitectRun], int]:
        stmt = (
            select(FrontendArchitectRun)
            .where(FrontendArchitectRun.organization_id == organization_id)
            .options(selectinload(FrontendArchitectRun.artifacts))
            .order_by(FrontendArchitectRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(FrontendArchitectRun).where(
            FrontendArchitectRun.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class FrontendArchitectArtifactRepository(BaseRepository[FrontendArchitectArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(FrontendArchitectArtifact, session)

    async def get_for_org(self, artifact_id: str, organization_id: str) -> FrontendArchitectArtifact | None:
        stmt = (
            select(FrontendArchitectArtifact)
            .join(
                FrontendArchitectRun,
                FrontendArchitectArtifact.run_id == FrontendArchitectRun.id,
            )
            .where(
                FrontendArchitectArtifact.id == artifact_id,
                FrontendArchitectRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
