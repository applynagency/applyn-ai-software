from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.qa_approval import QAApprovalArtifact, QAApprovalRun
from app.repositories.base import BaseRepository


class QAApprovalRunRepository(BaseRepository[QAApprovalRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(QAApprovalRun, session)

    async def get_with_artifact(self, run_id: str) -> QAApprovalRun | None:
        stmt = (
            select(QAApprovalRun)
            .where(QAApprovalRun.id == run_id)
            .options(selectinload(QAApprovalRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[QAApprovalRun], int]:
        stmt = (
            select(QAApprovalRun)
            .where(QAApprovalRun.requirement_id == requirement_id)
            .options(selectinload(QAApprovalRun.artifacts))
            .order_by(QAApprovalRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(QAApprovalRun).where(QAApprovalRun.requirement_id == requirement_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[QAApprovalRun], int]:
        stmt = (
            select(QAApprovalRun)
            .where(QAApprovalRun.organization_id == organization_id)
            .options(selectinload(QAApprovalRun.artifacts))
            .order_by(QAApprovalRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(QAApprovalRun).where(QAApprovalRun.organization_id == organization_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class QAApprovalArtifactRepository(BaseRepository[QAApprovalArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(QAApprovalArtifact, session)

    async def get_for_org(self, artifact_id: str, organization_id: str) -> QAApprovalArtifact | None:
        stmt = (
            select(QAApprovalArtifact)
            .join(QAApprovalRun, QAApprovalArtifact.run_id == QAApprovalRun.id)
            .where(
                QAApprovalArtifact.id == artifact_id,
                QAApprovalRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
