from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.security_test import SecurityTestArtifact, SecurityTestRun
from app.repositories.base import BaseRepository


class SecurityTestRunRepository(BaseRepository[SecurityTestRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(SecurityTestRun, session)

    async def get_with_artifact(self, run_id: str) -> SecurityTestRun | None:
        stmt = (
            select(SecurityTestRun)
            .where(SecurityTestRun.id == run_id)
            .options(selectinload(SecurityTestRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[SecurityTestRun], int]:
        stmt = (
            select(SecurityTestRun)
            .where(SecurityTestRun.requirement_id == requirement_id)
            .options(selectinload(SecurityTestRun.artifacts))
            .order_by(SecurityTestRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(SecurityTestRun).where(SecurityTestRun.requirement_id == requirement_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[SecurityTestRun], int]:
        stmt = (
            select(SecurityTestRun)
            .where(SecurityTestRun.organization_id == organization_id)
            .options(selectinload(SecurityTestRun.artifacts))
            .order_by(SecurityTestRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(SecurityTestRun).where(SecurityTestRun.organization_id == organization_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class SecurityTestArtifactRepository(BaseRepository[SecurityTestArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(SecurityTestArtifact, session)

    async def get_for_org(self, artifact_id: str, organization_id: str) -> SecurityTestArtifact | None:
        stmt = (
            select(SecurityTestArtifact)
            .join(SecurityTestRun, SecurityTestArtifact.run_id == SecurityTestRun.id)
            .where(
                SecurityTestArtifact.id == artifact_id,
                SecurityTestRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
