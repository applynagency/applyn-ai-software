import time
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError
from app.core.logging import get_logger
from app.models.approval import ApprovalRunStatus, WorkflowApprovalStatus
from app.models.user import User
from app.models.workflow_execution import ExecutionAgentKind, ExecutionStatus
from app.repositories.approval import ApprovalRunRepository
from app.repositories.audit import AuditLogRepository
from app.repositories.requirement import RequirementRepository
from app.repositories.workflow_execution import (
    WorkflowExecutionAgentRepository,
    WorkflowExecutionRepository,
    WorkflowExecutionStageRepository,
)
from app.schemas.workflow_execution import FullExecutionPlan, WorkflowExecuteRequest
from app.tenancy.guards import get_workflow_for_org
from app.tenancy.permissions import can_write_workflows
from app.workflows.dispatcher import AgentDispatcher
from app.workflows.plan_builder import ExecutionPlanBuilder

logger = get_logger(__name__)


class WorkflowExecutionEngine:
    """Orchestrates workflow-driven agent execution in stage order."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.execution_repo = WorkflowExecutionRepository(session)
        self.stage_repo = WorkflowExecutionStageRepository(session)
        self.agent_repo = WorkflowExecutionAgentRepository(session)
        self.requirement_repo = RequirementRepository(session)
        self.approval_run_repo = ApprovalRunRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.plan_builder = ExecutionPlanBuilder(session)
        self.dispatcher = AgentDispatcher()

    async def execute(
        self,
        workflow_id: str,
        data: WorkflowExecuteRequest,
        current_user: User,
        org_context: OrgContext,
    ):
        organization_id = org_context.requires_organization
        if not current_user.is_superuser and (
            not org_context.role or not can_write_workflows(org_context.role)
        ):
            raise ForbiddenError()

        await get_workflow_for_org(self.session, workflow_id, org_context)
        plan = await self.plan_builder.build(
            organization_id=organization_id,
            workflow_id=workflow_id,
            project_id=data.project_id,
            requirement_id=data.requirement_id,
            org_context=org_context,
        )

        requirement = await self.requirement_repo.get_by_id(data.requirement_id)
        requirement_content = requirement.content if requirement else ""

        execution = await self.execution_repo.create(
            organization_id=organization_id,
            workflow_id=workflow_id,
            project_id=data.project_id,
            requirement_id=data.requirement_id,
            status=ExecutionStatus.PENDING,
            started_by=current_user.id,
            execution_plan_json=plan.model_dump(),
        )

        stage_records = []
        agent_records = []
        for stage_plan in plan.stages:
            stage_record = await self.stage_repo.create(
                workflow_execution_id=execution.id,
                workflow_stage_id=stage_plan.stage_id,
                name=stage_plan.name,
                sequence=stage_plan.sequence,
                stage_type=stage_plan.stage_type,
                status=ExecutionStatus.PENDING,
            )
            stage_records.append((stage_plan, stage_record))
            for agent_plan in stage_plan.agents:
                agent_record = await self.agent_repo.create(
                    workflow_execution_id=execution.id,
                    workflow_execution_stage_id=stage_record.id,
                    agent_kind=ExecutionAgentKind.INTERNAL
                    if agent_plan.agent_kind == "internal"
                    else ExecutionAgentKind.CUSTOM,
                    internal_agent=agent_plan.internal_agent,
                    custom_agent_id=agent_plan.custom_agent_id,
                    team_id=agent_plan.team_id,
                    agent_name=agent_plan.name,
                    team_name=agent_plan.team_name,
                    execution_order=agent_plan.execution_order,
                    is_required=agent_plan.is_required,
                    status=ExecutionStatus.PENDING,
                    log_messages=[],
                )
                agent_records.append((agent_plan, agent_record))

        await self.audit_repo.log(
            action="workflow_execution_started",
            resource_type="workflow_execution",
            resource_id=execution.id,
            user_id=current_user.id,
            details={
                "workflow_id": workflow_id,
                "execution_id": execution.id,
                "requirement_id": data.requirement_id,
            },
        )

        execution_start = time.monotonic()
        now = datetime.now(UTC)
        await self.execution_repo.update(
            execution,
            status=ExecutionStatus.RUNNING,
            started_at=now,
        )

        return await self._run_stages(
            execution=execution,
            plan=plan,
            stage_records=stage_records,
            agent_records=agent_records,
            requirement_id=data.requirement_id,
            requirement_content=requirement_content,
            current_user=current_user,
            workflow_id=workflow_id,
            execution_start=execution_start,
            start_stage_index=0,
            start_agent_order=None,
        )

    async def resume_after_approval(
        self,
        *,
        requirement_id: str,
        current_user: User,
    ) -> None:
        waiting_executions = await self.execution_repo.list_waiting_for_requirement(
            requirement_id
        )
        for execution in waiting_executions:
            pause = (execution.execution_plan_json or {}).get("_workflow_pause") or {}
            start_stage_index = pause.get("resume_stage_index", 0)
            start_agent_order = pause.get("resume_agent_order")

            plan = FullExecutionPlan.model_validate(execution.execution_plan_json)
            requirement = await self.requirement_repo.get_by_id(requirement_id)
            requirement_content = requirement.content if requirement else ""

            execution = await self.execution_repo.get_with_details(execution.id)
            if not execution:
                continue

            stage_records = []
            agent_records = []
            for stage in sorted(execution.stages, key=lambda item: item.sequence):
                stage_plan = next(
                    planned for planned in plan.stages if planned.sequence == stage.sequence
                )
                stage_records.append((stage_plan, stage))
                for agent in sorted(stage.agents, key=lambda item: item.execution_order):
                    agent_plan = next(
                        planned
                        for planned in stage_plan.agents
                        if planned.execution_order == agent.execution_order
                        and (
                            planned.internal_agent == agent.internal_agent
                            or planned.name == agent.agent_name
                        )
                    )
                    agent_records.append((agent_plan, agent))

            execution_start = time.monotonic()
            now = datetime.now(UTC)
            await self.execution_repo.update(
                execution,
                status=ExecutionStatus.RUNNING,
                error_message=None,
            )

            await self.audit_repo.log(
                action="workflow_execution_resumed",
                resource_type="workflow_execution",
                resource_id=execution.id,
                user_id=current_user.id,
                details={"requirement_id": requirement_id},
            )

            await self._run_stages(
                execution=execution,
                plan=plan,
                stage_records=stage_records,
                agent_records=agent_records,
                requirement_id=requirement_id,
                requirement_content=requirement_content,
                current_user=current_user,
                workflow_id=execution.workflow_id,
                execution_start=execution_start,
                start_stage_index=start_stage_index,
                start_agent_order=start_agent_order,
            )

    async def _has_human_approval(self, requirement_id: str) -> bool:
        items, _ = await self.approval_run_repo.list_by_requirement(requirement_id, limit=100)
        return any(
            run.status == ApprovalRunStatus.COMPLETED
            and run.approval_status
            in (
                WorkflowApprovalStatus.APPROVED.value,
                WorkflowApprovalStatus.DEPLOYED.value,
            )
            and run.artifacts
            for run in items
        )

    async def _pause_for_approval(
        self,
        *,
        execution,
        stage_record,
        stage_plan,
        current_user: User,
        resume_stage_index: int,
        resume_agent_order: int | None,
        reason: str,
        execution_start: float,
    ):
        now = datetime.now(UTC)
        duration_ms = int((time.monotonic() - execution_start) * 1000)
        plan_data = dict(execution.execution_plan_json or {})
        plan_data["_workflow_pause"] = {
            "resume_stage_index": resume_stage_index,
            "resume_agent_order": resume_agent_order,
        }

        await self.stage_repo.update(
            stage_record,
            status=ExecutionStatus.WAITING_FOR_APPROVAL,
            completed_at=now,
            error_message=reason,
        )
        await self.execution_repo.update(
            execution,
            status=ExecutionStatus.WAITING_FOR_APPROVAL,
            execution_plan_json=plan_data,
            error_message=reason,
            duration_ms=duration_ms,
        )
        await self.audit_repo.log(
            action="workflow_execution_waiting_for_approval",
            resource_type="workflow_execution",
            resource_id=execution.id,
            user_id=current_user.id,
            details={
                "stage_id": stage_record.id,
                "stage_name": stage_plan.name,
                "approval_required": stage_plan.approval_required,
                "resume_stage_index": resume_stage_index,
                "resume_agent_order": resume_agent_order,
            },
        )

    def _requires_human_approval_gate(self, agent_plan) -> bool:
        return agent_plan.internal_agent == "deployment"

    async def _run_stages(
        self,
        *,
        execution,
        plan: FullExecutionPlan,
        stage_records,
        agent_records,
        requirement_id: str,
        requirement_content: str,
        current_user: User,
        workflow_id: str,
        execution_start: float,
        start_stage_index: int,
        start_agent_order: int | None,
    ):
        execution_failed = False
        failure_message: str | None = None

        for stage_index, (stage_plan, stage_record) in enumerate(stage_records):
            if stage_index < start_stage_index:
                continue

            if execution_failed:
                await self.stage_repo.update(stage_record, status=ExecutionStatus.SKIPPED)
                continue

            if stage_record.status == ExecutionStatus.COMPLETED:
                continue

            await self.audit_repo.log(
                action="stage_started",
                resource_type="workflow_execution_stage",
                resource_id=stage_record.id,
                user_id=current_user.id,
                details={"execution_id": execution.id, "stage_name": stage_plan.name},
            )

            stage_start = time.monotonic()
            stage_now = datetime.now(UTC)
            await self.stage_repo.update(
                stage_record,
                status=ExecutionStatus.RUNNING,
                started_at=stage_record.started_at or stage_now,
                error_message=None,
            )

            stage_agents = [
                (agent_plan, agent_record)
                for agent_plan, agent_record in agent_records
                if agent_record.workflow_execution_stage_id == stage_record.id
            ]
            stage_agents.sort(key=lambda item: item[1].execution_order)
            stage_failed = False

            for agent_plan, agent_record in stage_agents:
                if stage_index == start_stage_index and start_agent_order is not None:
                    if agent_record.execution_order < start_agent_order:
                        continue
                    if agent_record.status == ExecutionStatus.COMPLETED:
                        continue

                if stage_failed and execution_failed:
                    if agent_record.status == ExecutionStatus.PENDING:
                        await self.agent_repo.update(agent_record, status=ExecutionStatus.SKIPPED)
                    continue

                if (
                    self._requires_human_approval_gate(agent_plan)
                    and not await self._has_human_approval(requirement_id)
                ):
                    await self._pause_for_approval(
                        execution=execution,
                        stage_record=stage_record,
                        stage_plan=stage_plan,
                        current_user=current_user,
                        resume_stage_index=stage_index,
                        resume_agent_order=agent_record.execution_order,
                        reason="Deployment requires human approval before execution can continue",
                        execution_start=execution_start,
                    )
                    logger.info(
                        "workflow_execution_waiting_for_approval",
                        execution_id=execution.id,
                        stage_name=stage_plan.name,
                        agent_name=agent_plan.name,
                    )
                    return await self.execution_repo.get_with_details(execution.id)

                await self.audit_repo.log(
                    action="agent_started",
                    resource_type="workflow_execution_agent",
                    resource_id=agent_record.id,
                    user_id=current_user.id,
                    details={
                        "execution_id": execution.id,
                        "agent_name": agent_plan.name,
                    },
                )

                agent_start = time.monotonic()
                agent_now = datetime.now(UTC)
                await self.agent_repo.update(
                    agent_record,
                    status=ExecutionStatus.RUNNING,
                    started_at=agent_now,
                )

                if agent_plan.agent_kind == "internal":
                    result = await self.dispatcher.dispatch_internal(
                        internal_agent=agent_plan.internal_agent or "",
                        requirement_content=requirement_content,
                        session=self.session,
                        requirement_id=requirement_id,
                        user=current_user,
                    )
                else:
                    result = await self.dispatcher.dispatch_custom(
                        custom_agent_id=agent_plan.custom_agent_id or "",
                        prompt_template=agent_plan.prompt_template,
                        requirement_content=requirement_content,
                        session=self.session,
                    )

                agent_duration = int((time.monotonic() - agent_start) * 1000)
                agent_completed = datetime.now(UTC)

                if result.status == "skipped":
                    agent_status = ExecutionStatus.SKIPPED
                elif result.status == "failed":
                    agent_status = ExecutionStatus.FAILED
                else:
                    agent_status = ExecutionStatus.COMPLETED

                await self.agent_repo.update(
                    agent_record,
                    status=agent_status,
                    completed_at=agent_completed,
                    duration_ms=agent_duration,
                    tokens_used=result.tokens_used,
                    output_json=result.output,
                    error_message=result.error_message,
                    agent_run_id=result.agent_run_id,
                    log_messages=result.log_messages or [],
                )

                if agent_status in (ExecutionStatus.COMPLETED, ExecutionStatus.SKIPPED):
                    await self.audit_repo.log(
                        action="agent_completed",
                        resource_type="workflow_execution_agent",
                        resource_id=agent_record.id,
                        user_id=current_user.id,
                        details={
                            "execution_id": execution.id,
                            "status": agent_status.value,
                            "agent_name": agent_plan.name,
                        },
                    )
                else:
                    await self.audit_repo.log(
                        action="agent_completed",
                        resource_type="workflow_execution_agent",
                        resource_id=agent_record.id,
                        user_id=current_user.id,
                        details={
                            "execution_id": execution.id,
                            "status": agent_status.value,
                            "error": result.error_message,
                        },
                        status="failure",
                    )

                if agent_status == ExecutionStatus.FAILED and agent_plan.is_required:
                    stage_failed = True
                    execution_failed = True
                    failure_message = result.error_message or f"Required agent '{agent_plan.name}' failed"

            if stage_failed:
                stage_duration = int((time.monotonic() - stage_start) * 1000)
                stage_completed = datetime.now(UTC)
                await self.stage_repo.update(
                    stage_record,
                    status=ExecutionStatus.FAILED,
                    completed_at=stage_completed,
                    duration_ms=stage_duration,
                    error_message=failure_message,
                )
                await self.audit_repo.log(
                    action="stage_completed",
                    resource_type="workflow_execution_stage",
                    resource_id=stage_record.id,
                    user_id=current_user.id,
                    details={
                        "execution_id": execution.id,
                        "status": ExecutionStatus.FAILED.value,
                    },
                    status="failure",
                )
                continue

            if stage_plan.approval_required and not await self._has_human_approval(requirement_id):
                next_stage_index = stage_index + 1
                await self._pause_for_approval(
                    execution=execution,
                    stage_record=stage_record,
                    stage_plan=stage_plan,
                    current_user=current_user,
                    resume_stage_index=next_stage_index,
                    resume_agent_order=None,
                    reason="Stage requires human approval before execution can continue",
                    execution_start=execution_start,
                )
                logger.info(
                    "workflow_execution_waiting_for_approval",
                    execution_id=execution.id,
                    stage_name=stage_plan.name,
                )
                return await self.execution_repo.get_with_details(execution.id)

            stage_duration = int((time.monotonic() - stage_start) * 1000)
            stage_completed = datetime.now(UTC)
            await self.stage_repo.update(
                stage_record,
                status=ExecutionStatus.COMPLETED,
                completed_at=stage_completed,
                duration_ms=stage_duration,
                error_message=None,
            )
            await self.audit_repo.log(
                action="stage_completed",
                resource_type="workflow_execution_stage",
                resource_id=stage_record.id,
                user_id=current_user.id,
                details={
                    "execution_id": execution.id,
                    "status": ExecutionStatus.COMPLETED.value,
                },
            )

        total_duration = int((time.monotonic() - execution_start) * 1000)
        completed_now = datetime.now(UTC)
        final_status = ExecutionStatus.FAILED if execution_failed else ExecutionStatus.COMPLETED

        plan_data = dict(execution.execution_plan_json or {})
        plan_data.pop("_workflow_pause", None)

        await self.execution_repo.update(
            execution,
            status=final_status,
            completed_at=completed_now,
            duration_ms=total_duration,
            error_message=failure_message,
            execution_plan_json=plan_data,
        )

        audit_action = (
            "workflow_execution_failed"
            if final_status == ExecutionStatus.FAILED
            else "workflow_execution_completed"
        )
        await self.audit_repo.log(
            action=audit_action,
            resource_type="workflow_execution",
            resource_id=execution.id,
            user_id=current_user.id,
            details={
                "workflow_id": workflow_id,
                "duration_ms": total_duration,
                "status": final_status.value,
            },
            status="failure" if execution_failed else "success",
        )

        logger.info(
            "workflow_execution_finished",
            execution_id=execution.id,
            status=final_status.value,
            duration_ms=total_duration,
        )

        return await self.execution_repo.get_with_details(execution.id)
