from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lifecycle import (
    ApplicationVersion,
    RegenerationArtifact,
    RegenerationRun,
    ReleaseHistory,
)
from app.repositories.base import BaseRepository


class ApplicationVersionRepository(BaseRepository[ApplicationVersion]):
    def __init__(self, session: AsyncSession):
        super().__init__(ApplicationVersion, session)

    async def latest_for_requirement(self, requirement_id: str) -> ApplicationVersion | None:
        stmt = (
            select(ApplicationVersion)
            .where(ApplicationVersion.requirement_id == requirement_id)
            .order_by(ApplicationVersion.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_project(
        self, project_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[ApplicationVersion], int]:
        stmt = (
            select(ApplicationVersion)
            .where(ApplicationVersion.project_id == project_id)
            .order_by(ApplicationVersion.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(ApplicationVersion).where(ApplicationVersion.project_id == project_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class RegenerationRunRepository(BaseRepository[RegenerationRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(RegenerationRun, session)

    async def get_with_artifacts(self, run_id: str) -> RegenerationRun | None:
        stmt = (
            select(RegenerationRun)
            .where(RegenerationRun.id == run_id)
            .options(selectinload(RegenerationRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[RegenerationRun], int]:
        stmt = (
            select(RegenerationRun)
            .where(RegenerationRun.requirement_id == requirement_id)
            .options(selectinload(RegenerationRun.artifacts))
            .order_by(RegenerationRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(RegenerationRun).where(RegenerationRun.requirement_id == requirement_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_for_org(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[RegenerationRun], int]:
        stmt = (
            select(RegenerationRun)
            .where(RegenerationRun.organization_id == organization_id)
            .options(selectinload(RegenerationRun.artifacts))
            .order_by(RegenerationRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(RegenerationRun).where(RegenerationRun.organization_id == organization_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class RegenerationArtifactRepository(BaseRepository[RegenerationArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(RegenerationArtifact, session)

    async def get_for_org(
        self, artifact_id: str, organization_id: str
    ) -> RegenerationArtifact | None:
        stmt = (
            select(RegenerationArtifact)
            .join(RegenerationRun, RegenerationArtifact.run_id == RegenerationRun.id)
            .where(
                RegenerationArtifact.id == artifact_id,
                RegenerationRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class ReleaseHistoryRepository(BaseRepository[ReleaseHistory]):
    def __init__(self, session: AsyncSession):
        super().__init__(ReleaseHistory, session)

    async def list_by_project(
        self, project_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[ReleaseHistory], int]:
        stmt = (
            select(ReleaseHistory)
            .where(ReleaseHistory.project_id == project_id)
            .order_by(ReleaseHistory.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(ReleaseHistory).where(ReleaseHistory.project_id == project_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total
