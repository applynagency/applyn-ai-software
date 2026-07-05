from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.workflow import (
    WorkflowRuleRepository,
    WorkflowStageRepository,
    WorkflowStageTeamRepository,
)
from app.schemas.workflow import (
    WorkflowRuleCreate,
    WorkflowRuleResponse,
    WorkflowStageCreate,
    WorkflowStageResponse,
    WorkflowStageTeamAssign,
    WorkflowStageTeamResponse,
    WorkflowStageUpdate,
)
from app.tenancy.guards import get_stage_for_org, get_team_for_org, get_workflow_for_org
from app.tenancy.permissions import can_write_workflows
from app.workflows.rules_engine import WorkflowRulesEngine


class WorkflowStageService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.stage_repo = WorkflowStageRepository(self.session)
        self.assignment_repo = WorkflowStageTeamRepository(self.session)
        self.rule_repo = WorkflowRuleRepository(self.session)
        self.audit_repo = AuditLogRepository(self.session)
        self.rules_engine = WorkflowRulesEngine()

    async def create(
        self,
        workflow_id: str,
        data: WorkflowStageCreate,
        current_user: User,
        org_context: OrgContext,
    ) -> WorkflowStageResponse:
        await get_workflow_for_org(self.session, workflow_id, org_context)
        if not current_user.is_superuser and (
            not org_context.role or not can_write_workflows(org_context.role)
        ):
            raise ForbiddenError()

        stage = await self.stage_repo.create(
            workflow_id=workflow_id,
            name=data.name,
            description=data.description,
            sequence=data.sequence,
            stage_type=data.stage_type,
            approval_required=data.approval_required,
        )
        await self.audit_repo.log(
            action="stage_created",
            resource_type="workflow_stage",
            resource_id=stage.id,
            user_id=current_user.id,
            details={"workflow_id": workflow_id, "stage_id": stage.id},
        )
        return await self._stage_response(stage.id)

    async def update(
        self,
        stage_id: str,
        data: WorkflowStageUpdate,
        current_user: User,
        org_context: OrgContext,
    ) -> WorkflowStageResponse:
        stage = await get_stage_for_org(self.session, stage_id, org_context)
        if not current_user.is_superuser and (
            not org_context.role or not can_write_workflows(org_context.role)
        ):
            raise ForbiddenError()

        updated = await self.stage_repo.update(stage, **data.model_dump(exclude_none=True))
        await self.audit_repo.log(
            action="stage_updated",
            resource_type="workflow_stage",
            resource_id=stage_id,
            user_id=current_user.id,
            details={"workflow_id": stage.workflow_id, "stage_id": stage_id},
        )
        return await self._stage_response(updated.id)

    async def delete(
        self, stage_id: str, current_user: User, org_context: OrgContext
    ) -> None:
        stage = await get_stage_for_org(self.session, stage_id, org_context)
        if not current_user.is_superuser and (
            not org_context.role or not can_write_workflows(org_context.role)
        ):
            raise ForbiddenError()
        workflow_id = stage.workflow_id
        await self.stage_repo.hard_delete(stage)
        await self.audit_repo.log(
            action="stage_deleted",
            resource_type="workflow_stage",
            resource_id=stage_id,
            user_id=current_user.id,
            details={"workflow_id": workflow_id, "stage_id": stage_id},
        )

    async def assign_team(
        self,
        stage_id: str,
        data: WorkflowStageTeamAssign,
        current_user: User,
        org_context: OrgContext,
    ) -> WorkflowStageTeamResponse:
        stage = await get_stage_for_org(self.session, stage_id, org_context)
        await get_team_for_org(self.session, data.team_id, org_context)
        if not current_user.is_superuser and (
            not org_context.role or not can_write_workflows(org_context.role)
        ):
            raise ForbiddenError()

        existing = await self.assignment_repo.get_assignment(stage_id, data.team_id)
        if existing:
            raise ConflictError("Team is already assigned to this stage")

        assignment = await self.assignment_repo.create(
            workflow_stage_id=stage_id,
            team_id=data.team_id,
            execution_order=data.execution_order,
            is_required=data.is_required,
        )
        await self.audit_repo.log(
            action="team_assigned",
            resource_type="workflow_stage_team",
            resource_id=assignment.id,
            user_id=current_user.id,
            details={"workflow_id": stage.workflow_id, "stage_id": stage_id, "team_id": data.team_id},
        )
        loaded = await self.stage_repo.get_with_details(stage_id)
        assignment = next(
            (item for item in loaded.team_assignments if item.id == assignment.id),
            assignment,
        )
        return WorkflowStageTeamResponse(
            id=assignment.id,
            workflow_stage_id=assignment.workflow_stage_id,
            team_id=assignment.team_id,
            team_name=assignment.team.name if assignment.team else None,
            execution_order=assignment.execution_order,
            is_required=assignment.is_required,
            created_at=assignment.created_at,
        )

    async def unassign_team(
        self,
        stage_id: str,
        team_id: str,
        current_user: User,
        org_context: OrgContext,
    ) -> None:
        stage = await get_stage_for_org(self.session, stage_id, org_context)
        if not current_user.is_superuser and (
            not org_context.role or not can_write_workflows(org_context.role)
        ):
            raise ForbiddenError()
        assignment = await self.assignment_repo.get_assignment(stage_id, team_id)
        if not assignment:
            raise NotFoundError("WorkflowStageTeam", team_id)
        await self.assignment_repo.hard_delete(assignment)

    async def create_rule(
        self,
        workflow_id: str,
        data: WorkflowRuleCreate,
        current_user: User,
        org_context: OrgContext,
    ) -> WorkflowRuleResponse:
        await get_workflow_for_org(self.session, workflow_id, org_context)
        if not current_user.is_superuser and (
            not org_context.role or not can_write_workflows(org_context.role)
        ):
            raise ForbiddenError()

        configuration = self.rules_engine.validate_rule(data.rule_type, data.configuration_json)
        rule = await self.rule_repo.create(
            workflow_id=workflow_id,
            rule_type=data.rule_type,
            configuration_json=configuration,
        )
        await self.audit_repo.log(
            action="rule_created",
            resource_type="workflow_rule",
            resource_id=rule.id,
            user_id=current_user.id,
            details={"workflow_id": workflow_id, "rule_type": data.rule_type.value},
        )
        return WorkflowRuleResponse.model_validate(rule)

    async def _stage_response(self, stage_id: str) -> WorkflowStageResponse:
        stage = await self.stage_repo.get_with_details(stage_id)
        if not stage:
            raise NotFoundError("WorkflowStage", stage_id)
        assignments = sorted(stage.team_assignments or [], key=lambda item: item.execution_order)
        return WorkflowStageResponse(
            id=stage.id,
            workflow_id=stage.workflow_id,
            name=stage.name,
            description=stage.description,
            sequence=stage.sequence,
            stage_type=stage.stage_type,
            approval_required=stage.approval_required,
            created_at=stage.created_at,
            updated_at=stage.updated_at,
            team_count=len(assignments),
            team_assignments=[
                WorkflowStageTeamResponse(
                    id=assignment.id,
                    workflow_stage_id=assignment.workflow_stage_id,
                    team_id=assignment.team_id,
                    team_name=assignment.team.name if assignment.team else None,
                    execution_order=assignment.execution_order,
                    is_required=assignment.is_required,
                    created_at=assignment.created_at,
                )
                for assignment in assignments
            ],
        )
