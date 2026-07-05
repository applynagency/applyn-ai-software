from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import NotFoundError
from app.repositories.workflow import WorkflowRepository
from app.schemas.workflow import ExecutionPlanResponse, ExecutionPlanStage, ExecutionPlanTeam
from app.tenancy.guards import get_workflow_for_org


class WorkflowResolutionService:
    """Resolves a workflow into an ordered execution plan for Sprint 5."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.workflow_repo = WorkflowRepository(session)

    async def resolve(
        self, workflow_id: str, org_context: OrgContext
    ) -> ExecutionPlanResponse:
        workflow = await get_workflow_for_org(self.session, workflow_id, org_context)
        if not workflow:
            raise NotFoundError("Workflow", workflow_id)

        stages = sorted(workflow.stages, key=lambda stage: stage.sequence)
        plan_stages: list[ExecutionPlanStage] = []

        for stage in stages:
            teams = sorted(stage.team_assignments, key=lambda item: item.execution_order)
            plan_teams: list[ExecutionPlanTeam] = []
            team_names: list[str] = []

            for assignment in teams:
                team = assignment.team
                if not team:
                    continue
                team_names.append(team.name)
                agents = [
                    mapping.internal_agent
                    for mapping in sorted(
                        team.agent_mappings or [],
                        key=lambda mapping: mapping.execution_order,
                    )
                ]
                plan_teams.append(
                    ExecutionPlanTeam(
                        team_id=team.id,
                        name=team.name,
                        team_type=team.team_type.value,
                        execution_order=assignment.execution_order,
                        is_required=assignment.is_required,
                        agents=agents,
                    )
                )

            plan_stages.append(
                ExecutionPlanStage(
                    stage_id=stage.id,
                    name=stage.name,
                    sequence=stage.sequence,
                    stage_type=stage.stage_type.value,
                    approval_required=stage.approval_required,
                    teams=team_names,
                    team_details=plan_teams,
                )
            )

        return ExecutionPlanResponse(
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            status=workflow.status.value,
            stages=plan_stages,
            rules=[
                {
                    "rule_type": rule.rule_type.value,
                    "configuration_json": rule.configuration_json,
                }
                for rule in workflow.rules
            ],
        )
