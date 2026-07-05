from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_agents.resolution import AgentResolutionService
from app.auth.org_context import OrgContext
from app.repositories.ai_agent import AIAgentRepository
from app.repositories.team import TeamRepository
from app.schemas.workflow_execution import (
    ExecutionPlanAgentItem,
    ExecutionPlanStageItem,
    FullExecutionPlan,
)
from app.tenancy.guards import get_project_for_org, get_requirement_for_org, get_workflow_for_org
from app.workflows.dispatcher import AgentDispatcher
from app.workflows.resolution import WorkflowResolutionService


class ExecutionPlanBuilder:
    """Builds a unified workflow execution plan from resolution services."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.workflow_resolution = WorkflowResolutionService(session)
        self.agent_resolution = AgentResolutionService(session)
        self.team_repo = TeamRepository(session)
        self.ai_agent_repo = AIAgentRepository(session)
        self.dispatcher = AgentDispatcher()

    async def build(
        self,
        *,
        organization_id: str,
        workflow_id: str,
        project_id: str,
        requirement_id: str,
        org_context: OrgContext,
    ) -> FullExecutionPlan:
        await get_workflow_for_org(self.session, workflow_id, org_context)
        await get_project_for_org(self.session, project_id, org_context)
        requirement = await get_requirement_for_org(self.session, requirement_id, org_context)
        if requirement.project_id != project_id:
            from app.core.exceptions import ValidationError

            raise ValidationError("Requirement does not belong to the specified project")

        workflow_plan = await self.workflow_resolution.resolve(workflow_id, org_context)
        plan_stages: list[ExecutionPlanStageItem] = []

        for stage in sorted(workflow_plan.stages, key=lambda item: item.sequence):
            agents: list[ExecutionPlanAgentItem] = []

            for team_detail in sorted(stage.team_details, key=lambda item: item.execution_order):
                team = await self.team_repo.get_with_details(team_detail.team_id)
                mappings = sorted(
                    team.agent_mappings if team else [],
                    key=lambda mapping: mapping.execution_order,
                )
                for index, mapping in enumerate(mappings):
                    agents.append(
                        ExecutionPlanAgentItem(
                            agent_kind="internal",
                            internal_agent=mapping.internal_agent,
                            name=mapping.internal_agent.replace("_", " ").title(),
                            team_id=team_detail.team_id,
                            team_name=team_detail.name,
                            execution_order=team_detail.execution_order * 100 + mapping.execution_order,
                            is_required=team_detail.is_required and mapping.is_required,
                            is_implemented=self.dispatcher.is_implemented(mapping.internal_agent),
                        )
                    )

            stage_resolution = await self.agent_resolution.resolve(stage.stage_id, org_context)
            for custom in sorted(stage_resolution.custom_agents, key=lambda item: item.execution_order):
                agents.append(
                    ExecutionPlanAgentItem(
                        agent_kind="custom",
                        custom_agent_id=custom.agent_id,
                        name=custom.name,
                        team_id=custom.team_id,
                        team_name=custom.team_name,
                        execution_order=custom.execution_order,
                        is_required=custom.is_required,
                        is_implemented=True,
                        prompt_template=custom.prompt_template,
                    )
                )

            agents.sort(key=lambda item: item.execution_order)
            plan_stages.append(
                ExecutionPlanStageItem(
                    stage_id=stage.stage_id,
                    name=stage.name,
                    sequence=stage.sequence,
                    stage_type=stage.stage_type,
                    approval_required=stage.approval_required,
                    agents=agents,
                )
            )

        return FullExecutionPlan(
            organization_id=organization_id,
            workflow_id=workflow_id,
            workflow_name=workflow_plan.workflow_name,
            project_id=project_id,
            requirement_id=requirement_id,
            stages=plan_stages,
            rules=workflow_plan.rules,
        )
