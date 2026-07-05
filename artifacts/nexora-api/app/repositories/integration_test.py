from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.integration_test import IntegrationTestArtifact, IntegrationTestRun
from app.repositories.base import BaseRepository


class IntegrationTestRunRepository(BaseRepository[IntegrationTestRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(IntegrationTestRun, session)

    async def get_with_artifact(self, run_id: str) -> IntegrationTestRun | None:
        stmt = (
            select(IntegrationTestRun)
            .where(IntegrationTestRun.id == run_id)
            .options(selectinload(IntegrationTestRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[IntegrationTestRun], int]:
        stmt = (
            select(IntegrationTestRun)
            .where(IntegrationTestRun.requirement_id == requirement_id)
            .options(selectinload(IntegrationTestRun.artifacts))
            .order_by(IntegrationTestRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(IntegrationTestRun).where(IntegrationTestRun.requirement_id == requirement_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[IntegrationTestRun], int]:
        stmt = (
            select(IntegrationTestRun)
            .where(IntegrationTestRun.organization_id == organization_id)
            .options(selectinload(IntegrationTestRun.artifacts))
            .order_by(IntegrationTestRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(IntegrationTestRun).where(
            IntegrationTestRun.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class IntegrationTestArtifactRepository(BaseRepository[IntegrationTestArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(IntegrationTestArtifact, session)

    async def get_for_org(
        self, artifact_id: str, organization_id: str
    ) -> IntegrationTestArtifact | None:
        stmt = (
            select(IntegrationTestArtifact)
            .join(IntegrationTestRun, IntegrationTestArtifact.run_id == IntegrationTestRun.id)
            .where(
                IntegrationTestArtifact.id == artifact_id,
                IntegrationTestRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
