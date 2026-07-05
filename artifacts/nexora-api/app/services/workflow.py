from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.user import User
from app.models.workflow import Workflow, WorkflowStatus
from app.repositories.audit import AuditLogRepository
from app.repositories.workflow import WorkflowRepository
from app.schemas.workflow import (
    WorkflowAuditEventResponse,
    WorkflowAuditListResponse,
    WorkflowCreate,
    WorkflowDuplicateResponse,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowRuleResponse,
    WorkflowStageResponse,
    WorkflowStageTeamResponse,
    WorkflowUpdate,
)
from app.tenancy.guards import get_workflow_for_org
from app.tenancy.permissions import can_manage_workflows, can_read_workflows, can_write_workflows

logger = get_logger(__name__)


class WorkflowService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.workflow_repo = WorkflowRepository(session)
        self.audit_repo = AuditLogRepository(session)

    def _ensure_read(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_read_workflows(org_context.role)
        ):
            raise ForbiddenError()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_workflows(org_context.role)
        ):
            raise ForbiddenError()

    def _ensure_manage(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_manage_workflows(org_context.role)
        ):
            raise ForbiddenError()

    def _to_response(self, workflow: Workflow) -> WorkflowResponse:
        stages = sorted(workflow.stages or [], key=lambda stage: stage.sequence)
        stage_responses = []
        team_assignment_count = 0
        for stage in stages:
            assignments = sorted(stage.team_assignments or [], key=lambda item: item.execution_order)
            team_assignment_count += len(assignments)
            stage_responses.append(
                WorkflowStageResponse(
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
            )
        return WorkflowResponse(
            id=workflow.id,
            organization_id=workflow.organization_id,
            name=workflow.name,
            description=workflow.description,
            status=workflow.status,
            is_default=workflow.is_default,
            created_by=workflow.created_by,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
            stage_count=len(stages),
            team_assignment_count=team_assignment_count,
            rule_count=len(workflow.rules or []),
            stages=stage_responses,
            rules=[WorkflowRuleResponse.model_validate(rule) for rule in workflow.rules or []],
        )

    async def create(
        self, data: WorkflowCreate, current_user: User, org_context: OrgContext
    ) -> WorkflowResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(current_user, org_context)

        workflow = await self.workflow_repo.create(
            organization_id=organization_id,
            name=data.name,
            description=data.description,
            status=data.status,
            is_default=data.is_default,
            created_by=current_user.id,
        )
        workflow = await self.workflow_repo.get_with_details(workflow.id)
        await self.audit_repo.log(
            action="workflow_created",
            resource_type="workflow",
            resource_id=workflow.id,
            user_id=current_user.id,
            details={"workflow_id": workflow.id},
        )
        logger.info("workflow_created", workflow_id=workflow.id)
        return self._to_response(workflow)

    async def list_for_organization(
        self,
        current_user: User,
        org_context: OrgContext,
        *,
        status=None,
        offset: int = 0,
        limit: int = 50,
    ) -> WorkflowListResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        items, total = await self.workflow_repo.list_by_organization(
            organization_id, status=status, offset=offset, limit=limit
        )
        detailed = []
        for item in items:
            workflow = await self.workflow_repo.get_with_details(item.id)
            if workflow:
                detailed.append(self._to_response(workflow))
        return WorkflowListResponse(items=detailed, total=total)

    async def get(
        self, workflow_id: str, current_user: User, org_context: OrgContext
    ) -> WorkflowResponse:
        workflow = await get_workflow_for_org(self.session, workflow_id, org_context)
        self._ensure_read(current_user, org_context)
        return self._to_response(workflow)

    async def update(
        self, workflow_id: str, data: WorkflowUpdate, current_user: User, org_context: OrgContext
    ) -> WorkflowResponse:
        workflow = await get_workflow_for_org(self.session, workflow_id, org_context)
        self._ensure_write(current_user, org_context)
        update_data = data.model_dump(exclude_none=True)
        updated = await self.workflow_repo.update(workflow, **update_data)
        workflow = await self.workflow_repo.get_with_details(updated.id)
        await self.audit_repo.log(
            action="workflow_updated",
            resource_type="workflow",
            resource_id=workflow_id,
            user_id=current_user.id,
            details={"workflow_id": workflow_id, **update_data},
        )
        return self._to_response(workflow)

    async def archive(
        self, workflow_id: str, current_user: User, org_context: OrgContext
    ) -> WorkflowResponse:
        workflow = await get_workflow_for_org(self.session, workflow_id, org_context)
        self._ensure_manage(current_user, org_context)
        updated = await self.workflow_repo.update(workflow, status=WorkflowStatus.ARCHIVED)
        workflow = await self.workflow_repo.get_with_details(updated.id)
        await self.audit_repo.log(
            action="workflow_archived",
            resource_type="workflow",
            resource_id=workflow_id,
            user_id=current_user.id,
            details={"workflow_id": workflow_id},
        )
        return self._to_response(workflow)

    async def delete(
        self, workflow_id: str, current_user: User, org_context: OrgContext
    ) -> None:
        workflow = await get_workflow_for_org(self.session, workflow_id, org_context)
        self._ensure_manage(current_user, org_context)
        await self.workflow_repo.hard_delete(workflow)
        await self.audit_repo.log(
            action="workflow_deleted",
            resource_type="workflow",
            resource_id=workflow_id,
            user_id=current_user.id,
            details={"workflow_id": workflow_id},
        )

    async def duplicate(
        self, workflow_id: str, current_user: User, org_context: OrgContext
    ) -> WorkflowDuplicateResponse:
        from app.repositories.workflow import (
            WorkflowRuleRepository,
            WorkflowStageRepository,
            WorkflowStageTeamRepository,
        )

        source = await get_workflow_for_org(self.session, workflow_id, org_context)
        source = await self.workflow_repo.get_with_details(source.id)
        if not source:
            raise NotFoundError("Workflow", workflow_id)
        self._ensure_write(current_user, org_context)

        stage_repo = WorkflowStageRepository(self.session)
        assignment_repo = WorkflowStageTeamRepository(self.session)
        rule_repo = WorkflowRuleRepository(self.session)

        duplicate = await self.workflow_repo.create(
            organization_id=source.organization_id,
            name=f"{source.name} (Copy)",
            description=source.description,
            status=WorkflowStatus.DRAFT,
            is_default=False,
            created_by=current_user.id,
        )

        for stage in sorted(source.stages or [], key=lambda item: item.sequence):
            new_stage = await stage_repo.create(
                workflow_id=duplicate.id,
                name=stage.name,
                description=stage.description,
                sequence=stage.sequence,
                stage_type=stage.stage_type,
                approval_required=stage.approval_required,
            )
            for assignment in sorted(stage.team_assignments or [], key=lambda item: item.execution_order):
                await assignment_repo.create(
                    workflow_stage_id=new_stage.id,
                    team_id=assignment.team_id,
                    execution_order=assignment.execution_order,
                    is_required=assignment.is_required,
                )

        for rule in source.rules or []:
            await rule_repo.create(
                workflow_id=duplicate.id,
                rule_type=rule.rule_type,
                configuration_json=rule.configuration_json,
            )

        workflow = await self.workflow_repo.get_with_details(duplicate.id)
        await self.audit_repo.log(
            action="workflow_duplicated",
            resource_type="workflow",
            resource_id=duplicate.id,
            user_id=current_user.id,
            details={"workflow_id": duplicate.id, "source_workflow_id": workflow_id},
        )
        return WorkflowDuplicateResponse(workflow=self._to_response(workflow))

    async def list_audit_events(
        self, workflow_id: str, current_user: User, org_context: OrgContext
    ) -> WorkflowAuditListResponse:
        await get_workflow_for_org(self.session, workflow_id, org_context)
        self._ensure_read(current_user, org_context)
        items, total = await self.audit_repo.list_for_workflow(workflow_id)
        return WorkflowAuditListResponse(
            items=[WorkflowAuditEventResponse.model_validate(item) for item in items],
            total=total,
        )
