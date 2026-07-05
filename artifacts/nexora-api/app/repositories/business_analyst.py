from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.business_analyst import BusinessAnalystArtifact, BusinessAnalystRun
from app.repositories.base import BaseRepository


class BusinessAnalystRunRepository(BaseRepository[BusinessAnalystRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(BusinessAnalystRun, session)

    async def get_with_artifact(self, run_id: str) -> BusinessAnalystRun | None:
        stmt = (
            select(BusinessAnalystRun)
            .where(BusinessAnalystRun.id == run_id)
            .options(selectinload(BusinessAnalystRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[BusinessAnalystRun], int]:
        stmt = (
            select(BusinessAnalystRun)
            .where(BusinessAnalystRun.requirement_id == requirement_id)
            .options(selectinload(BusinessAnalystRun.artifacts))
            .order_by(BusinessAnalystRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(BusinessAnalystRun).where(
            BusinessAnalystRun.requirement_id == requirement_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[BusinessAnalystRun], int]:
        stmt = (
            select(BusinessAnalystRun)
            .where(BusinessAnalystRun.organization_id == organization_id)
            .options(selectinload(BusinessAnalystRun.artifacts))
            .order_by(BusinessAnalystRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(BusinessAnalystRun).where(
            BusinessAnalystRun.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class BusinessAnalystArtifactRepository(BaseRepository[BusinessAnalystArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(BusinessAnalystArtifact, session)

    async def get_for_org(self, artifact_id: str, organization_id: str) -> BusinessAnalystArtifact | None:
        stmt = (
            select(BusinessAnalystArtifact)
            .join(BusinessAnalystRun, BusinessAnalystArtifact.run_id == BusinessAnalystRun.id)
            .where(
                BusinessAnalystArtifact.id == artifact_id,
                BusinessAnalystRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_run_for_org(self, run_id: str, organization_id: str) -> BusinessAnalystRun | None:
        stmt = select(BusinessAnalystRun).where(
            BusinessAnalystRun.id == run_id,
            BusinessAnalystRun.organization_id == organization_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
