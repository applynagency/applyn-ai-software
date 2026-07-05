from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.uiux_designer import UIUXArtifact, UIUXRun
from app.repositories.base import BaseRepository


class UIUXRunRepository(BaseRepository[UIUXRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(UIUXRun, session)

    async def get_with_artifact(self, run_id: str) -> UIUXRun | None:
        stmt = (
            select(UIUXRun)
            .where(UIUXRun.id == run_id)
            .options(selectinload(UIUXRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[UIUXRun], int]:
        stmt = (
            select(UIUXRun)
            .where(UIUXRun.requirement_id == requirement_id)
            .options(selectinload(UIUXRun.artifacts))
            .order_by(UIUXRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(UIUXRun).where(UIUXRun.requirement_id == requirement_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[UIUXRun], int]:
        stmt = (
            select(UIUXRun)
            .where(UIUXRun.organization_id == organization_id)
            .options(selectinload(UIUXRun.artifacts))
            .order_by(UIUXRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(UIUXRun).where(UIUXRun.organization_id == organization_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class UIUXArtifactRepository(BaseRepository[UIUXArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(UIUXArtifact, session)

    async def get_for_org(self, artifact_id: str, organization_id: str) -> UIUXArtifact | None:
        stmt = (
            select(UIUXArtifact)
            .join(UIUXRun, UIUXArtifact.run_id == UIUXRun.id)
            .where(
                UIUXArtifact.id == artifact_id,
                UIUXRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
