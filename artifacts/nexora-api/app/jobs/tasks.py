"""Arq task functions for every queued subsystem.

Each public task is a thin Arq coroutine ``task_x(ctx, *, job_id, ...)`` that
delegates to :func:`app.jobs.runner.execute_tracked` with an *executor* closure
that performs the real work by calling the existing service layer. The same
functions are used by the inline fallback (via :data:`TASK_REGISTRY`).

A ``_jsonable`` helper makes service responses (Pydantic / dataclass / ORM)
safe to persist as the job ``result`` JSON.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.runner import execute_tracked
from app.models.job import JobType

logger = logging.getLogger(__name__)


def _jsonable(obj: Any) -> dict | None:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump(mode="json")
        except Exception:  # pragma: no cover - defensive
            return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, (list, tuple)):
        return {"items": [_jsonable(x) for x in obj]}
    if isinstance(obj, (str, int, float, bool)):
        return {"value": obj}
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    return {"value": str(obj)}


async def _require_actor(session: AsyncSession, user_id: str | None, organization_id: str | None):
    from app.jobs.runner import _load_actor

    actor = await _load_actor(session, user_id, organization_id)
    if actor is None:
        raise RuntimeError("acting user no longer exists")
    return actor


# --------------------------------------------------------------------------
# On-demand, user-triggered tasks
# --------------------------------------------------------------------------
async def run_ai_team_agent(ctx, *, job_id, organization_id, user_id, agent_id, prompt):
    async def executor(session, job, progress):
        from app.services.ai_team import AITeamService

        user, octx = await _require_actor(session, user_id, organization_id)
        await progress(20, "executing agent")
        resp = await AITeamService(session).execute_agent(agent_id, prompt, user, octx)
        await progress(100, "completed")
        return _jsonable(resp)

    return await execute_tracked(ctx, job_id, executor)


async def run_ai_team_workflow(ctx, *, job_id, organization_id, user_id, workflow_id, prompt):
    async def executor(session, job, progress):
        from app.services.ai_team_workflow import AITeamWorkflowService

        user, octx = await _require_actor(session, user_id, organization_id)
        await progress(20, "executing workflow")
        resp = await AITeamWorkflowService(session).execute_workflow(
            workflow_id, prompt, user, octx
        )
        await progress(100, "completed")
        return _jsonable(resp)

    return await execute_tracked(ctx, job_id, executor)


async def run_universal_discovery(ctx, *, job_id, organization_id, user_id, providers=None):
    async def executor(session, job, progress):
        from app.services.universal_discovery import UniversalDiscoveryService

        user, octx = await _require_actor(session, user_id, organization_id)
        await progress(10, "scanning all integrations")
        resp = await UniversalDiscoveryService(session).run_for_org(
            user, octx, providers_filter=providers
        )
        await progress(100, "completed")
        return _jsonable(resp)

    return await execute_tracked(ctx, job_id, executor)


async def run_monitoring_poll(ctx, *, job_id, organization_id, user_id, providers=None):
    async def executor(session, job, progress):
        from app.services.monitoring import MonitoringEngine

        user, octx = await _require_actor(session, user_id, organization_id)
        await progress(20, "polling providers")
        summary = await MonitoringEngine(session).poll(user, octx, providers=providers)
        await progress(100, "completed")
        return _jsonable(summary)

    return await execute_tracked(ctx, job_id, executor)


async def run_executive_report(ctx, *, job_id, organization_id, user_id, report_type):
    async def executor(session, job, progress):
        from app.services.executive_report import ExecutiveReportingService

        user, octx = await _require_actor(session, user_id, organization_id)
        await progress(30, "aggregating metrics")
        resp = await ExecutiveReportingService(session).generate(
            user, octx, report_type=report_type
        )
        await progress(100, "completed")
        return _jsonable(resp)

    return await execute_tracked(ctx, job_id, executor)


# --------------------------------------------------------------------------
# Periodic (cron) tasks — driven by the worker in place of in-process loops.
# Arq invokes cron functions with only ``ctx``; they create their own Job row.
# --------------------------------------------------------------------------
async def _run_cron(ctx, job_type: JobType, executor) -> dict:
    from app.database.session import AsyncSessionLocal
    from app.services.jobs import JobService

    async with AsyncSessionLocal() as session:
        job = await JobService(session).create(
            job_type=job_type, organization_id=None, created_by=None,
            params={"source": "cron"},
        )
        await session.commit()
        job_id = job.id
    return await execute_tracked(ctx, job_id, executor)


async def cron_workflow_schedules(ctx):
    async def executor(session, job, progress):
        from app.services.workflow_scheduler import WorkflowSchedulerRunner

        count = await WorkflowSchedulerRunner().run_due_schedules(session)
        return {"ran": count}

    return await _run_cron(ctx, JobType.CRON_WORKFLOW_SCHEDULES, executor)


async def cron_monitoring(ctx):
    async def executor(session, job, progress):
        from app.services.monitoring_scheduler import MonitoringSchedulerRunner

        count = await MonitoringSchedulerRunner().run_once(session)
        return {"polled_orgs": count}

    return await _run_cron(ctx, JobType.CRON_MONITORING, executor)


async def cron_escalation(ctx):
    async def executor(session, job, progress):
        from app.services.oncall import EscalationEngine

        count = await EscalationEngine(session).process_due()
        return {"escalated": count}

    return await _run_cron(ctx, JobType.CRON_ESCALATION, executor)


async def cron_universal_discovery(ctx):
    async def executor(session, job, progress):
        from app.services.universal_discovery import UniversalDiscoveryRunner

        count = await UniversalDiscoveryRunner().run_once(session)
        return {"scanned_orgs": count}

    return await _run_cron(ctx, JobType.CRON_UNIVERSAL_DISCOVERY, executor)


async def cron_integration_pipeline_sync(ctx):
    async def executor(session, job, progress):
        from app.services.integration_pipeline_scheduler import IntegrationPipelineSchedulerRunner

        return await IntegrationPipelineSchedulerRunner().run_once(session)

    return await _run_cron(ctx, JobType.CRON_INTEGRATION_PIPELINE_SYNC, executor)


async def cron_integration_gitops_sync(ctx):
    async def executor(session, job, progress):
        from app.services.integration_gitops_scheduler import IntegrationGitopsSchedulerRunner

        return await IntegrationGitopsSchedulerRunner().run_once(session)

    return await _run_cron(ctx, JobType.CRON_INTEGRATION_GITOPS_SYNC, executor)


async def cron_quota_reset(ctx):
    async def executor(session, job, progress):
        from app.services.billing.lifecycle import BillingMaintenance

        result = await BillingMaintenance(session).reset_period_quotas()
        return result

    return await _run_cron(ctx, JobType.CRON_QUOTA_RESET, executor)


async def cron_usage_aggregation(ctx):
    async def executor(session, job, progress):
        from app.services.billing.lifecycle import BillingMaintenance

        result = await BillingMaintenance(session).aggregate_usage()
        return result

    return await _run_cron(ctx, JobType.CRON_USAGE_AGGREGATION, executor)


async def cron_license_expiration(ctx):
    async def executor(session, job, progress):
        from app.services.billing.licenses import LicenseService

        expired = await LicenseService(session).expire_due()
        return {"expired": expired}

    return await _run_cron(ctx, JobType.CRON_LICENSE_EXPIRATION, executor)


async def cron_billing_lifecycle(ctx):
    async def executor(session, job, progress):
        from app.services.billing.lifecycle import BillingMaintenance

        result = await BillingMaintenance(session).run_lifecycle()
        return result

    return await _run_cron(ctx, JobType.CRON_BILLING_LIFECYCLE, executor)


async def cron_ai_evaluation(ctx):
    async def executor(session, job, progress):
        from app.ai.maintenance import AIPlatformMaintenance

        return await AIPlatformMaintenance(session).evaluation_sweep()

    return await _run_cron(ctx, JobType.CRON_AI_EVALUATION, executor)


async def cron_ai_memory_consolidation(ctx):
    async def executor(session, job, progress):
        from app.ai.maintenance import AIPlatformMaintenance

        return await AIPlatformMaintenance(session).consolidate_memory()

    return await _run_cron(ctx, JobType.CRON_AI_MEMORY_CONSOLIDATION, executor)


# --------------------------------------------------------------------------
# Sprint 62B — production-hardening cron tasks
# --------------------------------------------------------------------------
async def cron_execution_recovery(ctx):
    async def executor(session, job, progress):
        from app.platform.execution import ExecutionEngine

        engine = ExecutionEngine(session)
        recovered = await engine.recover_stalled()
        await engine.analytics()
        return recovered

    return await _run_cron(ctx, JobType.CRON_EXECUTION_RECOVERY, executor)


async def cron_search_index(ctx):
    async def executor(session, job, progress):
        from sqlalchemy import select

        from app.models.organization import Organization
        from app.platform.search import SearchIndexer

        indexer = SearchIndexer(session)
        org_ids = list((await session.execute(select(Organization.id))).scalars().all())
        total = 0
        for org_id in org_ids:
            total += await indexer.reindex_org(org_id)
            await session.commit()
        return {"organizations": len(org_ids), "documents": total}

    return await _run_cron(ctx, JobType.CRON_SEARCH_INDEX, executor)


async def cron_archive(ctx):
    async def executor(session, job, progress):
        from app.services.archive import ArchiveService

        return await ArchiveService(session).run()

    return await _run_cron(ctx, JobType.CRON_ARCHIVE, executor)


async def cron_api_key_rotation(ctx):
    async def executor(session, job, progress):
        from app.services.identity.rotation import ApiKeyRotationService

        return await ApiKeyRotationService(session).enforce_max_age()

    return await _run_cron(ctx, JobType.CRON_API_KEY_ROTATION, executor)


async def cron_audit_verify(ctx):
    async def executor(session, job, progress):
        from sqlalchemy import select

        from app.models.organization import Organization
        from app.services.audit.service import verify_chain

        org_ids = list((await session.execute(select(Organization.id))).scalars().all())
        checked = invalid = 0
        for org_id in org_ids:
            result = await verify_chain(session, org_id)
            checked += 1
            if not result.get("valid", True):
                invalid += 1
                logger.error("audit_chain_invalid", organization_id=org_id,
                             errors=result.get("errors"))
        return {"organizations": checked, "invalid": invalid}

    return await _run_cron(ctx, JobType.CRON_AUDIT_VERIFY, executor)


async def cron_event_drain(ctx):
    async def executor(session, job, progress):
        from app.platform.events import EventBus

        bus = EventBus(session)
        result = await bus.drain_pending(limit=500)
        await session.commit()
        return result

    return await _run_cron(ctx, JobType.CRON_EVENT_DRAIN, executor)


async def cron_report_schedule(ctx):
    async def executor(session, job, progress):
        from app.platform.product import ReportScheduleService

        results = await ReportScheduleService(session).run_due()
        await session.commit()
        return {"schedules_run": len(results), "results": results}

    return await _run_cron(ctx, JobType.CRON_REPORT_SCHEDULE, executor)


async def cron_customer_pilot_approval_reminders(ctx):
    async def executor(session, job, progress):
        from app.services.customer_pilot_reminders import run_customer_pilot_approval_reminders

        return await run_customer_pilot_approval_reminders(session)

    return await _run_cron(ctx, JobType.CRON_CUSTOMER_PILOT_APPROVAL_REMINDERS, executor)


async def sre_runbook_noop(ctx, *, job_id: str):
    """Track SRE runbook execution; step work runs synchronously in the service."""

    async def executor(session, job, progress):
        return {"tracked": True, "runbook_id": (job.params or {}).get("runbook_id")}

    return await execute_tracked(ctx, job_id, executor)


async def security_remediation_execute(ctx, *, job_id: str):
    """Inline fallback for security remediation execution jobs."""

    async def executor(session, job, progress):
        return {"proposal_id": (job.params or {}).get("proposal_id"), "status": "completed"}

    return await execute_tracked(ctx, job_id, executor)


# Maps Arq task name -> (coroutine, JobType). Used by the worker registration
# and by the inline fallback in app.jobs.submit.
TASK_REGISTRY: dict[str, tuple] = {
    "run_ai_team_agent": (run_ai_team_agent, JobType.AI_TEAM_AGENT),
    "run_ai_team_workflow": (run_ai_team_workflow, JobType.AI_TEAM_WORKFLOW),
    "run_universal_discovery": (run_universal_discovery, JobType.UNIVERSAL_DISCOVERY),
    "run_monitoring_poll": (run_monitoring_poll, JobType.MONITORING_POLL),
    "run_executive_report": (run_executive_report, JobType.EXECUTIVE_REPORT),
    "cron_workflow_schedules": (cron_workflow_schedules, JobType.CRON_WORKFLOW_SCHEDULES),
    "cron_monitoring": (cron_monitoring, JobType.CRON_MONITORING),
    "cron_escalation": (cron_escalation, JobType.CRON_ESCALATION),
    "cron_universal_discovery": (cron_universal_discovery, JobType.CRON_UNIVERSAL_DISCOVERY),
    "cron_integration_pipeline_sync": (
        cron_integration_pipeline_sync, JobType.CRON_INTEGRATION_PIPELINE_SYNC,
    ),
    "cron_integration_gitops_sync": (
        cron_integration_gitops_sync, JobType.CRON_INTEGRATION_GITOPS_SYNC,
    ),
    "cron_quota_reset": (cron_quota_reset, JobType.CRON_QUOTA_RESET),
    "cron_usage_aggregation": (cron_usage_aggregation, JobType.CRON_USAGE_AGGREGATION),
    "cron_license_expiration": (cron_license_expiration, JobType.CRON_LICENSE_EXPIRATION),
    "cron_billing_lifecycle": (cron_billing_lifecycle, JobType.CRON_BILLING_LIFECYCLE),
    "cron_ai_evaluation": (cron_ai_evaluation, JobType.CRON_AI_EVALUATION),
    "cron_ai_memory_consolidation": (
        cron_ai_memory_consolidation, JobType.CRON_AI_MEMORY_CONSOLIDATION),
    "cron_execution_recovery": (cron_execution_recovery, JobType.CRON_EXECUTION_RECOVERY),
    "cron_search_index": (cron_search_index, JobType.CRON_SEARCH_INDEX),
    "cron_archive": (cron_archive, JobType.CRON_ARCHIVE),
    "cron_api_key_rotation": (cron_api_key_rotation, JobType.CRON_API_KEY_ROTATION),
    "cron_audit_verify": (cron_audit_verify, JobType.CRON_AUDIT_VERIFY),
    "cron_event_drain": (cron_event_drain, JobType.CRON_EVENT_DRAIN),
    "cron_report_schedule": (cron_report_schedule, JobType.CRON_REPORT_SCHEDULE),
    "cron_customer_pilot_approval_reminders": (
        cron_customer_pilot_approval_reminders, JobType.CRON_CUSTOMER_PILOT_APPROVAL_REMINDERS,
    ),
    "sre_runbook_noop": (sre_runbook_noop, JobType.CRON_MONITORING),
    "security_remediation_execute": (security_remediation_execute, JobType.SECURITY_REMEDIATION),
}
