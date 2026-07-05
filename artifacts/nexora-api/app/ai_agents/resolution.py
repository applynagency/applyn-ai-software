from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import NotFoundError
from app.repositories.ai_agent import AIAgentWorkflowAssignmentRepository
from app.repositories.team import TeamRepository
from app.repositories.workflow import WorkflowStageRepository
from app.schemas.ai_agent import (
    StageAgentResolutionResponse,
    StageResolutionCustomAgent,
    StageResolutionTeam,
)
from app.tenancy.guards import get_stage_for_org


class AgentResolutionService:
    """Resolves teams and custom agents for a workflow stage. Execution deferred to Sprint 5."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.stage_repo = WorkflowStageRepository(session)
        self.assignment_repo = AIAgentWorkflowAssignmentRepository(session)
        self.team_repo = TeamRepository(session)

    async def resolve(
        self, workflow_stage_id: str, org_context: OrgContext
    ) -> StageAgentResolutionResponse:
        stage = await get_stage_for_org(self.session, workflow_stage_id, org_context)
        stage = await self.stage_repo.get_with_details(stage.id)
        if not stage:
            raise NotFoundError("WorkflowStage", workflow_stage_id)

        teams: list[StageResolutionTeam] = []
        for assignment in sorted(stage.team_assignments or [], key=lambda item: item.execution_order):
            team = assignment.team
            if not team:
                continue
            team_details = await self.team_repo.get_with_details(team.id)
            built_in_agents = []
            if team_details:
                built_in_agents = [
                    mapping.internal_agent
                    for mapping in sorted(
                        team_details.agent_mappings or [],
                        key=lambda mapping: mapping.execution_order,
                    )
                ]
            teams.append(
                StageResolutionTeam(
                    team_id=team.id,
                    name=team.name,
                    team_type=team.team_type.value,
                    execution_order=assignment.execution_order,
                    is_required=assignment.is_required,
                    built_in_agents=built_in_agents,
                )
            )

        custom_agents: list[StageResolutionCustomAgent] = []
        agent_assignments = await self.assignment_repo.list_for_stage(workflow_stage_id)
        for assignment in agent_assignments:
            agent = assignment.agent
            if not agent:
                continue
            custom_agents.append(
                StageResolutionCustomAgent(
                    agent_id=agent.id,
                    name=agent.name,
                    goal=agent.goal,
                    status=agent.status.value,
                    execution_order=assignment.execution_order,
                    is_required=assignment.is_required,
                    team_id=assignment.team_id,
                    team_name=assignment.team.name if assignment.team else None,
                    prompt_template=agent.prompt_template,
                    inputs=[
                        {
                            "input_name": item.input_name,
                            "input_type": item.input_type.value,
                            "required": item.required,
                        }
                        for item in agent.inputs or []
                    ],
                    outputs=[
                        {
                            "output_name": item.output_name,
                            "output_type": item.output_type.value,
                        }
                        for item in agent.outputs or []
                    ],
                )
            )

        workflow = stage.workflow
        return StageAgentResolutionResponse(
            workflow_stage_id=stage.id,
            stage_name=stage.name,
            workflow_id=workflow.id if workflow else stage.workflow_id,
            workflow_name=workflow.name if workflow else "",
            teams=teams,
            custom_agents=custom_agents,
        )
