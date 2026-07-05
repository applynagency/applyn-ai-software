from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.infrastructure_architect import (
    InfrastructureArchitectArtifact,
    InfrastructureArchitectRun,
)
from app.repositories.base import BaseRepository


class InfrastructureArchitectRunRepository(BaseRepository[InfrastructureArchitectRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(InfrastructureArchitectRun, session)

    async def get_with_artifact(self, run_id: str) -> InfrastructureArchitectRun | None:
        stmt = (
            select(InfrastructureArchitectRun)
            .where(InfrastructureArchitectRun.id == run_id)
            .options(selectinload(InfrastructureArchitectRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[InfrastructureArchitectRun], int]:
        stmt = (
            select(InfrastructureArchitectRun)
            .where(InfrastructureArchitectRun.requirement_id == requirement_id)
            .options(selectinload(InfrastructureArchitectRun.artifacts))
            .order_by(InfrastructureArchitectRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(InfrastructureArchitectRun).where(
            InfrastructureArchitectRun.requirement_id == requirement_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[InfrastructureArchitectRun], int]:
        stmt = (
            select(InfrastructureArchitectRun)
            .where(InfrastructureArchitectRun.organization_id == organization_id)
            .options(selectinload(InfrastructureArchitectRun.artifacts))
            .order_by(InfrastructureArchitectRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(InfrastructureArchitectRun).where(
            InfrastructureArchitectRun.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class InfrastructureArchitectArtifactRepository(BaseRepository[InfrastructureArchitectArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(InfrastructureArchitectArtifact, session)

    async def get_for_org(
        self, artifact_id: str, organization_id: str
    ) -> InfrastructureArchitectArtifact | None:
        stmt = (
            select(InfrastructureArchitectArtifact)
            .join(
                InfrastructureArchitectRun,
                InfrastructureArchitectArtifact.run_id == InfrastructureArchitectRun.id,
            )
            .where(
                InfrastructureArchitectArtifact.id == artifact_id,
                InfrastructureArchitectRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
