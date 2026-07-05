
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.workflow_execution import (
    WorkflowExecution,
    WorkflowExecutionAgent,
    WorkflowExecutionStage,
)
from app.repositories.base import BaseRepository


class WorkflowExecutionRepository(BaseRepository[WorkflowExecution]):
    def __init__(self, session: AsyncSession):
        super().__init__(WorkflowExecution, session)

    async def get_with_details(self, execution_id: str) -> WorkflowExecution | None:
        stmt = (
            select(WorkflowExecution)
            .where(WorkflowExecution.id == execution_id)
            .options(
                selectinload(WorkflowExecution.stages).selectinload(
                    WorkflowExecutionStage.agents
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
        workflow_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[WorkflowExecution], int]:
        filters = [WorkflowExecution.organization_id == organization_id]
        if workflow_id:
            filters.append(WorkflowExecution.workflow_id == workflow_id)
        # Eager-load stages + their agents so the page serializes without a
        # per-execution follow-up query (both relationships are selectin).
        return await self.list_all(
            filters=filters,
            offset=offset,
            limit=limit,
            options=[
                selectinload(WorkflowExecution.stages).selectinload(
                    WorkflowExecutionStage.agents
                ),
            ],
        )

    async def list_waiting_for_requirement(
        self, requirement_id: str
    ) -> list[WorkflowExecution]:
        from app.models.workflow_execution import ExecutionStatus

        stmt = select(WorkflowExecution).where(
            WorkflowExecution.requirement_id == requirement_id,
            WorkflowExecution.status == ExecutionStatus.WAITING_FOR_APPROVAL,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class WorkflowExecutionStageRepository(BaseRepository[WorkflowExecutionStage]):
    def __init__(self, session: AsyncSession):
        super().__init__(WorkflowExecutionStage, session)


class WorkflowExecutionAgentRepository(BaseRepository[WorkflowExecutionAgent]):
    def __init__(self, session: AsyncSession):
        super().__init__(WorkflowExecutionAgent, session)
