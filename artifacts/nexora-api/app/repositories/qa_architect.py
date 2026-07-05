from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.qa_architect import QAArchitectArtifact, QAArchitectRun
from app.repositories.base import BaseRepository


class QAArchitectRunRepository(BaseRepository[QAArchitectRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(QAArchitectRun, session)

    async def get_with_artifact(self, run_id: str) -> QAArchitectRun | None:
        stmt = (
            select(QAArchitectRun)
            .where(QAArchitectRun.id == run_id)
            .options(selectinload(QAArchitectRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[QAArchitectRun], int]:
        stmt = (
            select(QAArchitectRun)
            .where(QAArchitectRun.requirement_id == requirement_id)
            .options(selectinload(QAArchitectRun.artifacts))
            .order_by(QAArchitectRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(QAArchitectRun).where(QAArchitectRun.requirement_id == requirement_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[QAArchitectRun], int]:
        stmt = (
            select(QAArchitectRun)
            .where(QAArchitectRun.organization_id == organization_id)
            .options(selectinload(QAArchitectRun.artifacts))
            .order_by(QAArchitectRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(QAArchitectRun).where(
            QAArchitectRun.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class QAArchitectArtifactRepository(BaseRepository[QAArchitectArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(QAArchitectArtifact, session)

    async def get_for_org(self, artifact_id: str, organization_id: str) -> QAArchitectArtifact | None:
        stmt = (
            select(QAArchitectArtifact)
            .join(QAArchitectRun, QAArchitectArtifact.run_id == QAArchitectRun.id)
            .where(
                QAArchitectArtifact.id == artifact_id,
                QAArchitectRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
