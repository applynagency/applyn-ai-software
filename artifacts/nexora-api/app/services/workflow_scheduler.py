"""Sprint 38B — Scheduled Workflow Runs.

Adds time-based triggering on top of the Sprint 38A workflow engine. A schedule
stores a cron expression evaluated in a timezone; a background loop runs every
minute, finds active schedules whose ``next_run_at`` is due, executes the
workflow through the existing engine (``AITeamWorkflowService.run_workflow_core``
— no duplicated execution logic), records a normal workflow run tagged
``execution_source=SCHEDULED``, and advances ``next_run_at``.

This is purely scheduled execution: no autonomous decisions, continuous loops,
agent memory, or approval gates.
"""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import ForbiddenError, NexoraException
from app.core.logging import get_logger
from app.database.base import utcnow
from app.models.user import User
from app.repositories.ai_team import (
    AITeamWorkflowRepository,
    AITeamWorkflowScheduleRepository,
)
from app.repositories.audit import AuditLogRepository
from app.schemas.ai_team import (
    SCHEDULE_TYPES,
    AITeamWorkflowExecuteResponse,
    AITeamWorkflowScheduleCreate,
    AITeamWorkflowScheduleListResponse,
    AITeamWorkflowScheduleResponse,
    AITeamWorkflowScheduleUpdate,
)
from app.services.ai_team_workflow import AITeamWorkflowService
from app.tenancy.permissions import (
    can_manage_ai_teams,
    can_read_ai_teams,
    can_write_ai_teams,
)

logger = get_logger(__name__)


def validate_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or "UTC")
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        raise NexoraException(f"Unknown timezone: {tz_name}", status_code=422)


def compute_next_run(cron_expression: str, tz_name: str, base: datetime | None = None) -> datetime:
    """Return the next fire time strictly after ``base`` (UTC-aware).

    The cron expression is evaluated in the schedule's timezone so a "9am daily"
    schedule fires at 9am local time, then the result is converted to UTC for
    storage and comparison.
    """
    tz = validate_timezone(tz_name)
    base_utc = base or utcnow()
    base_local = base_utc.astimezone(tz)
    itr = croniter(cron_expression, base_local)
    nxt_local = itr.get_next(datetime)
    return nxt_local.astimezone(ZoneInfo("UTC"))


def validate_cron(expression: str) -> None:
    if not croniter.is_valid(expression):
        raise NexoraException(
            "Invalid cron expression. Use a 5-field cron (e.g. '0 9 * * *').",
            status_code=422,
        )


class AITeamWorkflowScheduleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.schedule_repo = AITeamWorkflowScheduleRepository(session)
        self.workflow_repo = AITeamWorkflowRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.workflow_service = AITeamWorkflowService(session)

    # ------------------------------------------------------------------ guards
    def _ensure_read(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    def _ensure_write(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_write_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    def _ensure_manage(self, current_user: User, org_context: OrgContext) -> None:
        if not current_user.is_superuser and (
            not org_context.role or not can_manage_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    # --------------------------------------------------------------- responses
    async def _to_response(self, schedule) -> AITeamWorkflowScheduleResponse:
        workflow = await self.workflow_repo.get_by_id(schedule.workflow_id)
        data = AITeamWorkflowScheduleResponse.model_validate(schedule)
        data.workflow_name = workflow.name if workflow else None
        return data

    def _validate_inputs(self, schedule_type: str, cron_expression: str, timezone: str) -> None:
        if schedule_type not in SCHEDULE_TYPES:
            raise NexoraException(
                f"Invalid schedule_type. Allowed: {sorted(SCHEDULE_TYPES)}", status_code=422
            )
        validate_cron(cron_expression)
        validate_timezone(timezone)

    # --------------------------------------------------------------- CRUD
    async def create_schedule(
        self,
        data: AITeamWorkflowScheduleCreate,
        current_user: User,
        org_context: OrgContext,
    ) -> AITeamWorkflowScheduleResponse:
        organization_id = org_context.requires_organization
        workflow = await self.workflow_repo.get_for_org(data.workflow_id, organization_id)
        if workflow is None:
            raise NexoraException("Workflow not found.", status_code=404)
        self._ensure_write(current_user, org_context)
        self._validate_inputs(data.schedule_type, data.cron_expression, data.timezone)

        next_run = (
            compute_next_run(data.cron_expression, data.timezone) if data.is_active else None
        )
        schedule = await self.schedule_repo.create(
            organization_id=organization_id,
            workflow_id=workflow.id,
            name=data.name,
            schedule_type=data.schedule_type,
            cron_expression=data.cron_expression,
            timezone=data.timezone,
            prompt_template=data.prompt_template,
            is_active=data.is_active,
            next_run_at=next_run,
        )
        await self.audit_repo.log(
            action="workflow_schedule_created",
            resource_type="ai_team_workflow_schedule",
            resource_id=schedule.id,
            user_id=current_user.id,
            details={"schedule_id": schedule.id, "workflow_id": workflow.id, "name": schedule.name},
        )
        logger.info("workflow_schedule_created", schedule_id=schedule.id, workflow_id=workflow.id)
        return await self._to_response(schedule)

    async def list_schedules(
        self,
        current_user: User,
        org_context: OrgContext,
        *,
        workflow_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> AITeamWorkflowScheduleListResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        items, total = await self.schedule_repo.list_by_organization(
            organization_id, workflow_id=workflow_id, offset=offset, limit=limit
        )
        # Enrich with workflow names (small N per org).
        workflows, _ = await self.workflow_repo.list_by_organization(
            organization_id, offset=0, limit=500
        )
        names = {w.id: w.name for w in workflows}
        responses = []
        for s in items:
            r = AITeamWorkflowScheduleResponse.model_validate(s)
            r.workflow_name = names.get(s.workflow_id)
            responses.append(r)
        return AITeamWorkflowScheduleListResponse(items=responses, total=total)

    async def get_schedule(
        self, schedule_id: str, current_user: User, org_context: OrgContext
    ) -> AITeamWorkflowScheduleResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(current_user, org_context)
        schedule = await self.schedule_repo.get_for_org(schedule_id, organization_id)
        if schedule is None:
            raise NexoraException("Schedule not found.", status_code=404)
        return await self._to_response(schedule)

    async def update_schedule(
        self,
        schedule_id: str,
        data: AITeamWorkflowScheduleUpdate,
        current_user: User,
        org_context: OrgContext,
    ) -> AITeamWorkflowScheduleResponse:
        organization_id = org_context.requires_organization
        schedule = await self.schedule_repo.get_for_org(schedule_id, organization_id)
        if schedule is None:
            raise NexoraException("Schedule not found.", status_code=404)
        self._ensure_write(current_user, org_context)

        fields = data.model_dump(exclude_none=True)
        new_type = fields.get("schedule_type", schedule.schedule_type)
        new_cron = fields.get("cron_expression", schedule.cron_expression)
        new_tz = fields.get("timezone", schedule.timezone)
        self._validate_inputs(new_type, new_cron, new_tz)

        if fields:
            await self.schedule_repo.update(schedule, **fields)

        # Recompute the next fire time whenever cadence/timezone/active changed.
        new_active = fields.get("is_active", schedule.is_active)
        if new_active:
            await self.schedule_repo.update(
                schedule, next_run_at=compute_next_run(new_cron, new_tz)
            )
        else:
            await self.schedule_repo.update(schedule, next_run_at=None)

        await self.audit_repo.log(
            action="workflow_schedule_updated",
            resource_type="ai_team_workflow_schedule",
            resource_id=schedule.id,
            user_id=current_user.id,
            details={"schedule_id": schedule.id, "workflow_id": schedule.workflow_id},
        )
        return await self._to_response(schedule)

    async def delete_schedule(
        self, schedule_id: str, current_user: User, org_context: OrgContext
    ) -> None:
        organization_id = org_context.requires_organization
        schedule = await self.schedule_repo.get_for_org(schedule_id, organization_id)
        if schedule is None:
            raise NexoraException("Schedule not found.", status_code=404)
        self._ensure_manage(current_user, org_context)
        workflow_id = schedule.workflow_id
        await self.schedule_repo.hard_delete(schedule)
        await self.audit_repo.log(
            action="workflow_schedule_deleted",
            resource_type="ai_team_workflow_schedule",
            resource_id=schedule_id,
            user_id=current_user.id,
            details={"schedule_id": schedule_id, "workflow_id": workflow_id},
        )

    async def run_now(
        self, schedule_id: str, current_user: User, org_context: OrgContext
    ) -> AITeamWorkflowExecuteResponse:
        organization_id = org_context.requires_organization
        schedule = await self.schedule_repo.get_for_org(schedule_id, organization_id)
        if schedule is None:
            raise NexoraException("Schedule not found.", status_code=404)
        self._ensure_write(current_user, org_context)
        workflow = await self.workflow_repo.get_for_org(schedule.workflow_id, organization_id)
        if workflow is None:
            raise NexoraException("Workflow not found.", status_code=404)

        effective_prompt = (schedule.prompt_template or "").strip() or (
            workflow.default_prompt or ""
        ).strip()
        if not effective_prompt:
            raise NexoraException(
                "Set a prompt template on the schedule or a default prompt on the workflow.",
                status_code=400,
            )

        result = await self.workflow_service.run_workflow_core(
            workflow,
            effective_prompt,
            organization_id,
            execution_source="SCHEDULED",
            actor_user_id=current_user.id,
        )
        # Manual run-now records the trigger time but does not disturb cadence.
        await self.schedule_repo.update(schedule, last_run_at=utcnow())
        await self.audit_repo.log(
            action="workflow_schedule_triggered",
            resource_type="ai_team_workflow_schedule",
            resource_id=schedule.id,
            user_id=current_user.id,
            details={
                "schedule_id": schedule.id,
                "workflow_id": workflow.id,
                "run_id": result.run_id,
                "trigger": "run_now",
            },
        )
        return result


class WorkflowSchedulerRunner:
    """Stateless tick executed by the background loop (and by tests directly)."""

    async def run_due_schedules(self, session: AsyncSession, now: datetime | None = None) -> int:
        now = now or utcnow()
        repo = AITeamWorkflowScheduleRepository(session)
        workflow_repo = AITeamWorkflowRepository(session)
        audit_repo = AuditLogRepository(session)
        workflow_service = AITeamWorkflowService(session)

        due = await repo.list_due(now)
        triggered = 0
        for schedule in due:
            # Atomically claim this due window before doing any work. With
            # multiple uvicorn workers each running a scheduler loop, only the
            # worker that wins this conditional update executes; the rest skip,
            # preventing duplicate runs. Advancing next_run_at here also avoids
            # re-triggering a misconfigured schedule on the next tick.
            next_run = compute_next_run(
                schedule.cron_expression, schedule.timezone, now
            )
            claimed = await repo.claim_due(
                schedule.id, schedule.next_run_at, next_run, now
            )
            await session.commit()
            if not claimed:
                continue

            workflow = await workflow_repo.get_for_org(
                schedule.workflow_id, schedule.organization_id
            )
            prompt = (schedule.prompt_template or "").strip() or (
                (workflow.default_prompt or "").strip() if workflow else ""
            )
            try:
                if workflow and workflow.is_active and prompt:
                    result = await workflow_service.run_workflow_core(
                        workflow,
                        prompt,
                        schedule.organization_id,
                        execution_source="SCHEDULED",
                        actor_user_id=None,
                    )
                    await audit_repo.log(
                        action="workflow_schedule_triggered",
                        resource_type="ai_team_workflow_schedule",
                        resource_id=schedule.id,
                        user_id=None,
                        details={
                            "schedule_id": schedule.id,
                            "workflow_id": schedule.workflow_id,
                            "run_id": result.run_id,
                            "trigger": "scheduled",
                        },
                    )
                    await session.commit()
                    triggered += 1
                else:
                    logger.info(
                        "workflow_schedule_skipped",
                        schedule_id=schedule.id,
                        reason="inactive_workflow_or_empty_prompt",
                    )
            except NexoraException:
                # run_workflow_core already persisted (and committed) a FAILED
                # run; the claim already advanced next_run_at, so just continue.
                logger.info("workflow_schedule_run_failed", schedule_id=schedule.id)
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(
                    "workflow_schedule_error", schedule_id=schedule.id, error=str(exc)
                )
        return triggered


async def workflow_scheduler_loop() -> None:
    """Background loop: poll for due schedules on a fixed cadence."""
    from app.database.session import AsyncSessionLocal

    runner = WorkflowSchedulerRunner()
    interval = max(5, settings.WORKFLOW_SCHEDULER_INTERVAL_SECONDS)
    logger.info("workflow_scheduler_started", interval_seconds=interval)
    from app.observability.tracing import start_as_current_span
    from app.redis.locks import scheduler_lock

    while True:
        try:
            async with scheduler_lock("workflow") as token:
                if token is not None:
                    with start_as_current_span("scheduler.workflow", kind="consumer"):
                        async with AsyncSessionLocal() as session:
                            count = await runner.run_due_schedules(session)
                            if count:
                                logger.info("workflow_scheduler_tick", triggered=count)
        except asyncio.CancelledError:
            logger.info("workflow_scheduler_stopped")
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("workflow_scheduler_tick_failed", error=str(exc))
        await asyncio.sleep(interval)
