from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.observability_agent import ObservabilityArtifact, ObservabilityRun
from app.repositories.base import BaseRepository


class ObservabilityRunRepository(BaseRepository[ObservabilityRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(ObservabilityRun, session)

    async def get_with_artifact(self, run_id: str) -> ObservabilityRun | None:
        stmt = (
            select(ObservabilityRun)
            .where(ObservabilityRun.id == run_id)
            .options(selectinload(ObservabilityRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[ObservabilityRun], int]:
        stmt = (
            select(ObservabilityRun)
            .where(ObservabilityRun.requirement_id == requirement_id)
            .options(selectinload(ObservabilityRun.artifacts))
            .order_by(ObservabilityRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(ObservabilityRun).where(
            ObservabilityRun.requirement_id == requirement_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[ObservabilityRun], int]:
        stmt = (
            select(ObservabilityRun)
            .where(ObservabilityRun.organization_id == organization_id)
            .options(selectinload(ObservabilityRun.artifacts))
            .order_by(ObservabilityRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(ObservabilityRun).where(
            ObservabilityRun.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class ObservabilityArtifactRepository(BaseRepository[ObservabilityArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(ObservabilityArtifact, session)

    async def get_for_org(
        self, artifact_id: str, organization_id: str
    ) -> ObservabilityArtifact | None:
        stmt = (
            select(ObservabilityArtifact)
            .join(ObservabilityRun, ObservabilityArtifact.run_id == ObservabilityRun.id)
            .where(
                ObservabilityArtifact.id == artifact_id,
                ObservabilityRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
