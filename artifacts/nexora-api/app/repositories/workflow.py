
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.team import Team
from app.models.workflow import (
    Workflow,
    WorkflowRule,
    WorkflowStage,
    WorkflowStageTeam,
    WorkflowStatus,
)
from app.repositories.base import BaseRepository


class WorkflowRepository(BaseRepository[Workflow]):
    def __init__(self, session: AsyncSession):
        super().__init__(Workflow, session)

    async def get_with_details(self, workflow_id: str) -> Workflow | None:
        stmt = (
            select(Workflow)
            .where(Workflow.id == workflow_id)
            .options(
                selectinload(Workflow.stages).selectinload(WorkflowStage.team_assignments).selectinload(
                    WorkflowStageTeam.team
                ).selectinload(Team.agent_mappings),
                selectinload(Workflow.rules),
            )
            .execution_options(populate_existing=True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_organization(
        self,
        organization_id: str,
        *,
        status: WorkflowStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Workflow], int]:
        filters = [Workflow.organization_id == organization_id]
        if status:
            filters.append(Workflow.status == status)
        return await self.list_all(filters=filters, offset=offset, limit=limit)


class WorkflowStageRepository(BaseRepository[WorkflowStage]):
    def __init__(self, session: AsyncSession):
        super().__init__(WorkflowStage, session)

    async def get_with_details(self, stage_id: str) -> WorkflowStage | None:
        stmt = (
            select(WorkflowStage)
            .where(WorkflowStage.id == stage_id)
            .options(
                selectinload(WorkflowStage.team_assignments).selectinload(WorkflowStageTeam.team),
                selectinload(WorkflowStage.workflow),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_workflow(self, workflow_id: str) -> list[WorkflowStage]:
        items, _ = await self.list_all(
            filters=[WorkflowStage.workflow_id == workflow_id],
            limit=500,
        )
        return sorted(items, key=lambda stage: stage.sequence)


class WorkflowStageTeamRepository(BaseRepository[WorkflowStageTeam]):
    def __init__(self, session: AsyncSession):
        super().__init__(WorkflowStageTeam, session)

    async def get_assignment(
        self, stage_id: str, team_id: str
    ) -> WorkflowStageTeam | None:
        stmt = select(WorkflowStageTeam).where(
            WorkflowStageTeam.workflow_stage_id == stage_id,
            WorkflowStageTeam.team_id == team_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_for_team(self, team_id: str) -> int:
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(WorkflowStageTeam)
            .where(WorkflowStageTeam.team_id == team_id)
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())


class WorkflowRuleRepository(BaseRepository[WorkflowRule]):
    def __init__(self, session: AsyncSession):
        super().__init__(WorkflowRule, session)

    async def list_for_workflow(self, workflow_id: str) -> list[WorkflowRule]:
        items, _ = await self.list_all(
            filters=[WorkflowRule.workflow_id == workflow_id],
            limit=100,
        )
        return items
