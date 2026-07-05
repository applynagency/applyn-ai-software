"""Sprint 42D — data access for advisory deployment-safety analyses."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment_safety import DeploymentSafetyAnalysis
from app.repositories.base import BaseRepository


class DeploymentSafetyRepository(BaseRepository[DeploymentSafetyAnalysis]):
    def __init__(self, session: AsyncSession):
        super().__init__(DeploymentSafetyAnalysis, session)

    async def get_for_org(
        self, analysis_id: str, organization_id: str
    ) -> DeploymentSafetyAnalysis | None:
        stmt = select(DeploymentSafetyAnalysis).where(
            DeploymentSafetyAnalysis.id == analysis_id,
            DeploymentSafetyAnalysis.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(
        self, organization_id: str, *, limit: int = 100
    ) -> list[DeploymentSafetyAnalysis]:
        stmt = (
            select(DeploymentSafetyAnalysis)
            .where(DeploymentSafetyAnalysis.organization_id == organization_id)
            .order_by(DeploymentSafetyAnalysis.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())
