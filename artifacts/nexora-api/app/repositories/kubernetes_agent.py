from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.kubernetes_agent import KubernetesArtifact, KubernetesRun
from app.repositories.base import BaseRepository


class KubernetesRunRepository(BaseRepository[KubernetesRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(KubernetesRun, session)

    async def get_with_artifact(self, run_id: str) -> KubernetesRun | None:
        stmt = (
            select(KubernetesRun)
            .where(KubernetesRun.id == run_id)
            .options(selectinload(KubernetesRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[KubernetesRun], int]:
        stmt = (
            select(KubernetesRun)
            .where(KubernetesRun.requirement_id == requirement_id)
            .options(selectinload(KubernetesRun.artifacts))
            .order_by(KubernetesRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(KubernetesRun).where(KubernetesRun.requirement_id == requirement_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[KubernetesRun], int]:
        stmt = (
            select(KubernetesRun)
            .where(KubernetesRun.organization_id == organization_id)
            .options(selectinload(KubernetesRun.artifacts))
            .order_by(KubernetesRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(KubernetesRun).where(KubernetesRun.organization_id == organization_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class KubernetesArtifactRepository(BaseRepository[KubernetesArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(KubernetesArtifact, session)

    async def get_for_org(self, artifact_id: str, organization_id: str) -> KubernetesArtifact | None:
        stmt = (
            select(KubernetesArtifact)
            .join(KubernetesRun, KubernetesArtifact.run_id == KubernetesRun.id)
            .where(
                KubernetesArtifact.id == artifact_id,
                KubernetesRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
