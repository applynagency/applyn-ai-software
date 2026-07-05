from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.sre_approval import SreApprovalArtifact, SreApprovalRun
from app.repositories.base import BaseRepository


class SreApprovalRunRepository(BaseRepository[SreApprovalRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(SreApprovalRun, session)

    async def get_with_artifact(self, run_id: str) -> SreApprovalRun | None:
        stmt = (
            select(SreApprovalRun)
            .where(SreApprovalRun.id == run_id)
            .options(selectinload(SreApprovalRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[SreApprovalRun], int]:
        stmt = (
            select(SreApprovalRun)
            .where(SreApprovalRun.requirement_id == requirement_id)
            .options(selectinload(SreApprovalRun.artifacts))
            .order_by(SreApprovalRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(SreApprovalRun).where(SreApprovalRun.requirement_id == requirement_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[SreApprovalRun], int]:
        stmt = (
            select(SreApprovalRun)
            .where(SreApprovalRun.organization_id == organization_id)
            .options(selectinload(SreApprovalRun.artifacts))
            .order_by(SreApprovalRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(SreApprovalRun).where(
            SreApprovalRun.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class SreApprovalArtifactRepository(BaseRepository[SreApprovalArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(SreApprovalArtifact, session)

    async def get_for_org(self, artifact_id: str, organization_id: str) -> SreApprovalArtifact | None:
        stmt = (
            select(SreApprovalArtifact)
            .join(SreApprovalRun, SreApprovalArtifact.run_id == SreApprovalRun.id)
            .where(
                SreApprovalArtifact.id == artifact_id,
                SreApprovalRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
