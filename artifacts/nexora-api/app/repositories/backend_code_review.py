from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.backend_code_review import BackendCodeReviewArtifact, BackendCodeReviewRun
from app.repositories.base import BaseRepository


class BackendCodeReviewRunRepository(BaseRepository[BackendCodeReviewRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(BackendCodeReviewRun, session)

    async def get_with_artifact(self, run_id: str) -> BackendCodeReviewRun | None:
        stmt = (
            select(BackendCodeReviewRun)
            .where(BackendCodeReviewRun.id == run_id)
            .options(selectinload(BackendCodeReviewRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[BackendCodeReviewRun], int]:
        stmt = (
            select(BackendCodeReviewRun)
            .where(BackendCodeReviewRun.requirement_id == requirement_id)
            .options(selectinload(BackendCodeReviewRun.artifacts))
            .order_by(BackendCodeReviewRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(BackendCodeReviewRun).where(
            BackendCodeReviewRun.requirement_id == requirement_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[BackendCodeReviewRun], int]:
        stmt = (
            select(BackendCodeReviewRun)
            .where(BackendCodeReviewRun.organization_id == organization_id)
            .options(selectinload(BackendCodeReviewRun.artifacts))
            .order_by(BackendCodeReviewRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(BackendCodeReviewRun).where(
            BackendCodeReviewRun.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class BackendCodeReviewArtifactRepository(BaseRepository[BackendCodeReviewArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(BackendCodeReviewArtifact, session)

    async def get_for_org(
        self, artifact_id: str, organization_id: str
    ) -> BackendCodeReviewArtifact | None:
        stmt = (
            select(BackendCodeReviewArtifact)
            .join(
                BackendCodeReviewRun,
                BackendCodeReviewArtifact.run_id == BackendCodeReviewRun.id,
            )
            .where(
                BackendCodeReviewArtifact.id == artifact_id,
                BackendCodeReviewRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
