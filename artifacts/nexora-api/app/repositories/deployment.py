from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.deployment import DeploymentArtifact, DeploymentLog, DeploymentRun
from app.repositories.base import BaseRepository


class DeploymentRunRepository(BaseRepository[DeploymentRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(DeploymentRun, session)

    async def get_with_artifact(self, run_id: str) -> DeploymentRun | None:
        stmt = (
            select(DeploymentRun)
            .where(DeploymentRun.id == run_id)
            .options(
                selectinload(DeploymentRun.artifacts),
                selectinload(DeploymentRun.logs),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[DeploymentRun], int]:
        stmt = (
            select(DeploymentRun)
            .where(DeploymentRun.requirement_id == requirement_id)
            .options(selectinload(DeploymentRun.artifacts))
            .order_by(DeploymentRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(DeploymentRun).where(DeploymentRun.requirement_id == requirement_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[DeploymentRun], int]:
        stmt = (
            select(DeploymentRun)
            .where(DeploymentRun.organization_id == organization_id)
            .options(selectinload(DeploymentRun.artifacts))
            .order_by(DeploymentRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(DeploymentRun).where(
            DeploymentRun.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class DeploymentArtifactRepository(BaseRepository[DeploymentArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(DeploymentArtifact, session)

    async def get_for_org(
        self, artifact_id: str, organization_id: str
    ) -> DeploymentArtifact | None:
        stmt = (
            select(DeploymentArtifact)
            .join(DeploymentRun, DeploymentArtifact.run_id == DeploymentRun.id)
            .where(
                DeploymentArtifact.id == artifact_id,
                DeploymentRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class DeploymentLogRepository(BaseRepository[DeploymentLog]):
    def __init__(self, session: AsyncSession):
        super().__init__(DeploymentLog, session)

    async def list_by_run(
        self, run_id: str, *, offset: int = 0, limit: int = 200
    ) -> tuple[list[DeploymentLog], int]:
        stmt = (
            select(DeploymentLog)
            .where(DeploymentLog.run_id == run_id)
            .order_by(DeploymentLog.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(DeploymentLog).where(DeploymentLog.run_id == run_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_for_org_run(
        self, run_id: str, organization_id: str, *, offset: int = 0, limit: int = 200
    ) -> tuple[list[DeploymentLog], int]:
        stmt = (
            select(DeploymentLog)
            .join(DeploymentRun, DeploymentLog.run_id == DeploymentRun.id)
            .where(
                DeploymentLog.run_id == run_id,
                DeploymentRun.organization_id == organization_id,
            )
            .order_by(DeploymentLog.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = (
            select(DeploymentLog)
            .join(DeploymentRun, DeploymentLog.run_id == DeploymentRun.id)
            .where(
                DeploymentLog.run_id == run_id,
                DeploymentRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total
