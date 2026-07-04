
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import AgentOutput, AgentRun, AgentRunStatus, AgentType
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.workspace import Workspace
from app.repositories.base import BaseRepository


class AgentRunRepository(BaseRepository[AgentRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(AgentRun, session)

    async def get_with_outputs(self, run_id: str) -> AgentRun | None:
        stmt = (
            select(AgentRun)
            .where(AgentRun.id == run_id)
            .options(selectinload(AgentRun.outputs))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_organization(
        self, organization_id: str, offset: int = 0, limit: int = 50
    ) -> tuple[list[AgentRun], int]:
        org_filter = Workspace.organization_id == organization_id
        count_stmt = (
            select(func.count(AgentRun.id))
            .select_from(AgentRun)
            .join(Requirement, AgentRun.requirement_id == Requirement.id)
            .join(Project, Requirement.project_id == Project.id)
            .join(Workspace, Project.workspace_id == Workspace.id)
            .where(org_filter)
        )
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        stmt = (
            select(AgentRun)
            .join(Requirement, AgentRun.requirement_id == Requirement.id)
            .join(Project, Requirement.project_id == Project.id)
            .join(Workspace, Project.workspace_id == Workspace.id)
            .where(org_filter)
            .order_by(AgentRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all()), total

    async def list_by_requirement(
        self, requirement_id: str, offset: int = 0, limit: int = 50
    ) -> tuple[list[AgentRun], int]:
        return await self.list_all(
            filters=[AgentRun.requirement_id == requirement_id],
            offset=offset,
            limit=limit,
        )

    async def get_latest_for_requirement(
        self, requirement_id: str, agent_type: AgentType = AgentType.PRODUCT_OWNER
    ) -> AgentRun | None:
        stmt = (
            select(AgentRun)
            .where(
                AgentRun.requirement_id == requirement_id,
                AgentRun.agent_type == agent_type,
                AgentRun.status == AgentRunStatus.COMPLETED,
            )
            .order_by(AgentRun.created_at.desc())
            .limit(1)
            .options(selectinload(AgentRun.outputs))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class AgentOutputRepository(BaseRepository[AgentOutput]):
    def __init__(self, session: AsyncSession):
        super().__init__(AgentOutput, session)

    async def get_by_run(self, run_id: str) -> list[AgentOutput]:
        stmt = select(AgentOutput).where(AgentOutput.agent_run_id == run_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
