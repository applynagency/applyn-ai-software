from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.user import User
from app.models.workflow_execution import WorkflowExecution
from app.repositories.audit import AuditLogRepository
from app.repositories.workflow_execution import WorkflowExecutionRepository
from app.schemas.workflow_execution import (
    WorkflowExecuteRequest,
    WorkflowExecutionAgentResponse,
    WorkflowExecutionAuditEventResponse,
    WorkflowExecutionAuditListResponse,
    WorkflowExecutionListResponse,
    WorkflowExecutionResponse,
    WorkflowExecutionStageResponse,
    WorkflowExecutionStatusResponse,
)
from app.tenancy.guards import get_workflow_execution_for_org
from app.tenancy.permissions import can_read_workflows, can_write_workflows
from app.workflows.execution_engine import WorkflowExecutionEngine


class WorkflowExecutionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.execution_repo = WorkflowExecutionRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.engine = WorkflowExecutionEngine(session)

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

    def _to_response(self, execution: WorkflowExecution) -> WorkflowExecutionResponse:
        stages = sorted(execution.stages or [], key=lambda stage: stage.sequence)
        agent_count = sum(len(stage.agents or []) for stage in stages)
        return WorkflowExecutionResponse(
            id=execution.id,
            organization_id=execution.organization_id,
            workflow_id=execution.workflow_id,
            project_id=execution.project_id,
            requirement_id=execution.requirement_id,
            status=execution.status,
            started_by=execution.started_by,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            duration_ms=execution.duration_ms,
            error_message=execution.error_message,
            execution_plan_json=execution.execution_plan_json or {},
            created_at=execution.created_at,
            updated_at=execution.updated_at,
            stage_count=len(stages),
            agent_count=agent_count,
            stages=[
                WorkflowExecutionStageResponse(
                    id=stage.id,
                    workflow_execution_id=stage.workflow_execution_id,
                    workflow_stage_id=stage.workflow_stage_id,
                    name=stage.name,
                    sequence=stage.sequence,
                    stage_type=stage.stage_type,
                    status=stage.status,
                    started_at=stage.started_at,
                    completed_at=stage.completed_at,
                    duration_ms=stage.duration_ms,
                    error_message=stage.error_message,
                    created_at=stage.created_at,
                    updated_at=stage.updated_at,
                    agents=[
                        WorkflowExecutionAgentResponse.model_validate(agent)
                        for agent in sorted(stage.agents or [], key=lambda item: item.execution_order)
                    ],
                )
                for stage in stages
            ],
        )

    async def execute(
        self,
        workflow_id: str,
        data: WorkflowExecuteRequest,
        current_user: User,
        org_context: OrgContext,
    ) -> WorkflowExecutionResponse:
        self._ensure_write(current_user, org_context)
        execution = await self.engine.execute(workflow_id, data, current_user, org_context)
        if not execution:
            raise NotFoundError("WorkflowExecution", workflow_id)
        return self._to_response(execution)

    async def list_for_organization(
        self,
        current_user: User,
        org_context: OrgContext,
        *,
        workflow_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> WorkflowExecutionListResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        items, total = await self.execution_repo.list_by_organization(
            organization_id, workflow_id=workflow_id, offset=offset, limit=limit
        )
        # Stages/agents are eager-loaded by the repository; serialize directly.
        detailed = [self._to_response(item) for item in items]
        return WorkflowExecutionListResponse(items=detailed, total=total)

    async def get(
        self, execution_id: str, current_user: User, org_context: OrgContext
    ) -> WorkflowExecutionResponse:
        execution = await get_workflow_execution_for_org(self.session, execution_id, org_context)
        self._ensure_read(current_user, org_context)
        return self._to_response(execution)

    async def get_status(
        self, execution_id: str, current_user: User, org_context: OrgContext
    ) -> WorkflowExecutionStatusResponse:
        execution = await get_workflow_execution_for_org(self.session, execution_id, org_context)
        self._ensure_read(current_user, org_context)
        response = self._to_response(execution)
        return WorkflowExecutionStatusResponse(
            id=response.id,
            status=response.status,
            workflow_id=response.workflow_id,
            requirement_id=response.requirement_id,
            started_at=response.started_at,
            completed_at=response.completed_at,
            duration_ms=response.duration_ms,
            error_message=response.error_message,
            stages=response.stages,
        )

    async def list_audit_events(
        self, execution_id: str, current_user: User, org_context: OrgContext
    ) -> WorkflowExecutionAuditListResponse:
        await get_workflow_execution_for_org(self.session, execution_id, org_context)
        self._ensure_read(current_user, org_context)
        items, total = await self.audit_repo.list_for_workflow_execution(execution_id)
        return WorkflowExecutionAuditListResponse(
            items=[WorkflowExecutionAuditEventResponse.model_validate(item) for item in items],
            total=total,
        )
