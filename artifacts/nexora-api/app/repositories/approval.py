from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.approval import ApprovalArtifact, ApprovalRun
from app.repositories.base import BaseRepository


class ApprovalRunRepository(BaseRepository[ApprovalRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(ApprovalRun, session)

    async def get_with_artifact(self, run_id: str) -> ApprovalRun | None:
        stmt = (
            select(ApprovalRun)
            .where(ApprovalRun.id == run_id)
            .options(selectinload(ApprovalRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[ApprovalRun], int]:
        stmt = (
            select(ApprovalRun)
            .where(ApprovalRun.requirement_id == requirement_id)
            .options(selectinload(ApprovalRun.artifacts))
            .order_by(ApprovalRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(ApprovalRun).where(ApprovalRun.requirement_id == requirement_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[ApprovalRun], int]:
        stmt = (
            select(ApprovalRun)
            .where(ApprovalRun.organization_id == organization_id)
            .options(selectinload(ApprovalRun.artifacts))
            .order_by(ApprovalRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(ApprovalRun).where(ApprovalRun.organization_id == organization_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class ApprovalArtifactRepository(BaseRepository[ApprovalArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(ApprovalArtifact, session)

    async def get_for_org(
        self, artifact_id: str, organization_id: str
    ) -> ApprovalArtifact | None:
        stmt = (
            select(ApprovalArtifact)
            .join(ApprovalRun, ApprovalArtifact.run_id == ApprovalRun.id)
            .where(
                ApprovalArtifact.id == artifact_id,
                ApprovalRun.organization_id == organization_id,
            )
            .options(selectinload(ApprovalArtifact.run))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
