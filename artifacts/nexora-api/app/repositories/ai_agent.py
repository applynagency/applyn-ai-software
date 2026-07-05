
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ai_agent import (
    AIAgent,
    AIAgentInput,
    AIAgentOutput,
    AIAgentResponsibility,
    AIAgentStatus,
    AIAgentWorkflowAssignment,
)
from app.models.workflow import WorkflowStage
from app.repositories.base import BaseRepository


class AIAgentRepository(BaseRepository[AIAgent]):
    def __init__(self, session: AsyncSession):
        super().__init__(AIAgent, session)

    async def get_with_details(self, agent_id: str) -> AIAgent | None:
        stmt = (
            select(AIAgent)
            .where(AIAgent.id == agent_id)
            .options(
                selectinload(AIAgent.inputs),
                selectinload(AIAgent.outputs),
                selectinload(AIAgent.responsibilities),
                selectinload(AIAgent.workflow_assignments)
                .selectinload(AIAgentWorkflowAssignment.stage)
                .selectinload(WorkflowStage.workflow),
                selectinload(AIAgent.workflow_assignments).selectinload(
                    AIAgentWorkflowAssignment.team
                ),
            )
            .execution_options(populate_existing=True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_organization(
        self,
        organization_id: str,
        *,
        status: AIAgentStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[AIAgent], int]:
        filters = [AIAgent.organization_id == organization_id]
        if status:
            filters.append(AIAgent.status == status)
        return await self.list_all(filters=filters, offset=offset, limit=limit)


class AIAgentInputRepository(BaseRepository[AIAgentInput]):
    def __init__(self, session: AsyncSession):
        super().__init__(AIAgentInput, session)

    async def get_for_agent(self, input_id: str, agent_id: str) -> AIAgentInput | None:
        stmt = select(AIAgentInput).where(
            AIAgentInput.id == input_id,
            AIAgentInput.agent_id == agent_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class AIAgentOutputRepository(BaseRepository[AIAgentOutput]):
    def __init__(self, session: AsyncSession):
        super().__init__(AIAgentOutput, session)

    async def get_for_agent(self, output_id: str, agent_id: str) -> AIAgentOutput | None:
        stmt = select(AIAgentOutput).where(
            AIAgentOutput.id == output_id,
            AIAgentOutput.agent_id == agent_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class AIAgentResponsibilityRepository(BaseRepository[AIAgentResponsibility]):
    def __init__(self, session: AsyncSession):
        super().__init__(AIAgentResponsibility, session)

    async def get_for_agent(
        self, responsibility_id: str, agent_id: str
    ) -> AIAgentResponsibility | None:
        stmt = select(AIAgentResponsibility).where(
            AIAgentResponsibility.id == responsibility_id,
            AIAgentResponsibility.agent_id == agent_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class AIAgentWorkflowAssignmentRepository(BaseRepository[AIAgentWorkflowAssignment]):
    def __init__(self, session: AsyncSession):
        super().__init__(AIAgentWorkflowAssignment, session)

    async def get_assignment(
        self, agent_id: str, workflow_stage_id: str, team_id: str | None
    ) -> AIAgentWorkflowAssignment | None:
        stmt = select(AIAgentWorkflowAssignment).where(
            AIAgentWorkflowAssignment.agent_id == agent_id,
            AIAgentWorkflowAssignment.workflow_stage_id == workflow_stage_id,
        )
        if team_id:
            stmt = stmt.where(AIAgentWorkflowAssignment.team_id == team_id)
        else:
            stmt = stmt.where(AIAgentWorkflowAssignment.team_id.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_stage(self, workflow_stage_id: str) -> list[AIAgentWorkflowAssignment]:
        stmt = (
            select(AIAgentWorkflowAssignment)
            .where(AIAgentWorkflowAssignment.workflow_stage_id == workflow_stage_id)
            .options(
                selectinload(AIAgentWorkflowAssignment.agent).selectinload(AIAgent.inputs),
                selectinload(AIAgentWorkflowAssignment.agent).selectinload(AIAgent.outputs),
                selectinload(AIAgentWorkflowAssignment.team),
            )
            .order_by(AIAgentWorkflowAssignment.execution_order)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_with_details(self, assignment_id: str) -> AIAgentWorkflowAssignment | None:
        stmt = (
            select(AIAgentWorkflowAssignment)
            .where(AIAgentWorkflowAssignment.id == assignment_id)
            .options(
                selectinload(AIAgentWorkflowAssignment.stage).selectinload(WorkflowStage.workflow),
                selectinload(AIAgentWorkflowAssignment.team),
                selectinload(AIAgentWorkflowAssignment.agent),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
