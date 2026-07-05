from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.docker_agent import DockerAgentArtifact, DockerAgentRun
from app.repositories.base import BaseRepository


class DockerAgentRunRepository(BaseRepository[DockerAgentRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(DockerAgentRun, session)

    async def get_with_artifact(self, run_id: str) -> DockerAgentRun | None:
        stmt = (
            select(DockerAgentRun)
            .where(DockerAgentRun.id == run_id)
            .options(selectinload(DockerAgentRun.artifacts))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_requirement(
        self, requirement_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[DockerAgentRun], int]:
        stmt = (
            select(DockerAgentRun)
            .where(DockerAgentRun.requirement_id == requirement_id)
            .options(selectinload(DockerAgentRun.artifacts))
            .order_by(DockerAgentRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(DockerAgentRun).where(DockerAgentRun.requirement_id == requirement_id)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total

    async def list_by_organization(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[DockerAgentRun], int]:
        stmt = (
            select(DockerAgentRun)
            .where(DockerAgentRun.organization_id == organization_id)
            .options(selectinload(DockerAgentRun.artifacts))
            .order_by(DockerAgentRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(DockerAgentRun).where(
            DockerAgentRun.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        count_result = await self.session.execute(count_stmt)
        total = len(list(count_result.scalars().all()))
        return items, total


class DockerAgentArtifactRepository(BaseRepository[DockerAgentArtifact]):
    def __init__(self, session: AsyncSession):
        super().__init__(DockerAgentArtifact, session)

    async def get_for_org(
        self, artifact_id: str, organization_id: str
    ) -> DockerAgentArtifact | None:
        stmt = (
            select(DockerAgentArtifact)
            .join(DockerAgentRun, DockerAgentArtifact.run_id == DockerAgentRun.id)
            .where(
                DockerAgentArtifact.id == artifact_id,
                DockerAgentRun.organization_id == organization_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
