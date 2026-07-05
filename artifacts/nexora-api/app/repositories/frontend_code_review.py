from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.frontend_code_review import FrontendCodeReviewArtifact, FrontendCodeReviewRun
from app.repositories.base import BaseRepository


class FrontendCodeReviewRunRepository(BaseRepository[FrontendCodeReviewRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(FrontendCodeReviewRun, session)

    async def get_with_artifact(self, run_id: str) -> FrontendCodeReviewRun | None:
        stmt = (
            select(FrontendCodeReviewRun)
            .where(FrontendCodeReviewRun.id == run_id)
            .options(selectinload(FrontendCodeReviewRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[FrontendCodeReviewRun], int]:
        stmt = (
            select(FrontendCodeReviewRun)
            .where(FrontendCodeReviewRun.requirement_id == requirement_id)
            .options(selectinload(FrontendCodeReviewRun.artifacts))
            .order_by(FrontendCodeReviewRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(FrontendCodeReviewRun).where(
            FrontendCodeReviewRun.requirement_id == requirement_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[FrontendCodeReviewRun], int]:
        stmt = (
            select(FrontendCodeReviewRun)
            .where(FrontendCodeReviewRun.organization_id == organization_id)
            .options(selectinload(FrontendCodeReviewRun.artifacts))
            .order_by(FrontendCodeReviewRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(FrontendCodeReviewRun).where(
            FrontendCodeReviewRun.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class FrontendCodeReviewArtifactRepository(BaseRepository[FrontendCodeReviewArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(FrontendCodeReviewArtifact, session)

    async def get_for_org(
        self, artifact_id: str, organization_id: str
    ) -> FrontendCodeReviewArtifact | None:
        stmt = (
            select(FrontendCodeReviewArtifact)
            .join(
                FrontendCodeReviewRun,
                FrontendCodeReviewArtifact.run_id == FrontendCodeReviewRun.id,
            )
            .where(
                FrontendCodeReviewArtifact.id == artifact_id,
                FrontendCodeReviewRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
