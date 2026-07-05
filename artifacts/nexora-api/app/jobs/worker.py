"""Arq worker entrypoint.

Run with::

    arq app.jobs.worker.WorkerSettings

The worker executes both the on-demand jobs (enqueued by the API) and the
periodic cron jobs that replace the in-process scheduler loops when
``JOB_QUEUE_ENABLED`` is on. Each cron job respects its subsystem's existing
``*_ENABLED`` flag.

Importing this module requires ``arq`` to be installed (only the worker process
needs it; the API imports the queue lazily).
"""

from __future__ import annotations

from arq import cron

from app.core.config import settings
from app.jobs import tasks
from app.jobs.queue import redis_settings

# On-demand tasks the API enqueues. Kept in lockstep with tasks.TASK_REGISTRY
# (legacy ``run_discovery`` was removed during discovery convergence).
ON_DEMAND_TASKS = [
    tasks.run_ai_team_agent,
    tasks.run_ai_team_workflow,
    tasks.run_universal_discovery,
    tasks.run_monitoring_poll,
    tasks.run_executive_report,
]


def _cron_spec(seconds: int) -> dict:
    """Translate an interval (seconds) into Arq cron field kwargs."""
    seconds = max(1, int(seconds))
    if seconds < 60:
        step = max(1, seconds)
        return {"second": set(range(0, 60, step))}
    minutes = max(1, seconds // 60)
    return {"minute": set(range(0, 60, minutes)), "second": 0}


def _build_cron_jobs() -> list:
    jobs = []
    if settings.WORKFLOW_SCHEDULER_ENABLED:
        jobs.append(cron(tasks.cron_workflow_schedules,
                         **_cron_spec(settings.JOB_CRON_WORKFLOW_SECONDS), unique=True))
    if settings.MONITORING_ENABLED:
        jobs.append(cron(tasks.cron_monitoring,
                         **_cron_spec(settings.JOB_CRON_MONITORING_SECONDS), unique=True))
    if settings.ESCALATION_ENABLED:
        jobs.append(cron(tasks.cron_escalation,
                         **_cron_spec(settings.JOB_CRON_ESCALATION_SECONDS), unique=True))
    if settings.UNIVERSAL_DISCOVERY_ENABLED:
        jobs.append(cron(tasks.cron_universal_discovery,
                         **_cron_spec(settings.JOB_CRON_UNIVERSAL_DISCOVERY_SECONDS), unique=True))
    if settings.INTEGRATION_PIPELINE_SYNC_ENABLED:
        jobs.append(cron(tasks.cron_integration_pipeline_sync,
                         **_cron_spec(settings.JOB_CRON_INTEGRATION_PIPELINE_SYNC_SECONDS),
                         unique=True))
    if settings.INTEGRATION_GITOPS_SYNC_ENABLED:
        jobs.append(cron(tasks.cron_integration_gitops_sync,
                         **_cron_spec(settings.JOB_CRON_INTEGRATION_GITOPS_SYNC_SECONDS),
                         unique=True))
    if settings.BILLING_ENABLED:
        jobs.append(cron(tasks.cron_quota_reset,
                         **_cron_spec(settings.JOB_CRON_QUOTA_RESET_SECONDS), unique=True))
        jobs.append(cron(tasks.cron_usage_aggregation,
                         **_cron_spec(settings.JOB_CRON_USAGE_AGGREGATION_SECONDS), unique=True))
        jobs.append(cron(tasks.cron_license_expiration,
                         **_cron_spec(settings.JOB_CRON_LICENSE_EXPIRATION_SECONDS), unique=True))
        jobs.append(cron(tasks.cron_billing_lifecycle,
                         **_cron_spec(settings.JOB_CRON_BILLING_LIFECYCLE_SECONDS), unique=True))
    if settings.AI_PLATFORM_ENABLED:
        jobs.append(cron(tasks.cron_ai_evaluation,
                         **_cron_spec(settings.JOB_CRON_AI_EVALUATION_SECONDS), unique=True))
        jobs.append(cron(tasks.cron_ai_memory_consolidation,
                         **_cron_spec(settings.JOB_CRON_AI_MEMORY_CONSOLIDATION_SECONDS),
                         unique=True))
    # Sprint 62B — production-hardening periodic jobs.
    if settings.HARDENING_ENABLED:
        jobs.append(cron(tasks.cron_execution_recovery,
                         **_cron_spec(settings.JOB_CRON_EXECUTION_RECOVERY_SECONDS),
                         unique=True))
        if settings.EVENT_CONSUMER_ENABLED:
            jobs.append(cron(tasks.cron_event_drain,
                             **_cron_spec(settings.EVENT_CONSUMER_POLL_SECONDS), unique=True))
        if settings.SEARCH_INDEX_ENABLED:
            jobs.append(cron(tasks.cron_search_index,
                             **_cron_spec(settings.JOB_CRON_SEARCH_INDEX_SECONDS),
                             unique=True))
        if settings.ARCHIVE_ENABLED:
            jobs.append(cron(tasks.cron_archive,
                             **_cron_spec(settings.JOB_CRON_ARCHIVE_SECONDS), unique=True))
        if settings.IDENTITY_ENABLED:
            jobs.append(cron(tasks.cron_api_key_rotation,
                             **_cron_spec(settings.JOB_CRON_API_KEY_ROTATION_SECONDS),
                             unique=True))
        jobs.append(cron(tasks.cron_audit_verify,
                         **_cron_spec(settings.JOB_CRON_AUDIT_VERIFY_SECONDS), unique=True))
    if settings.PRODUCT_EXCELLENCE_ENABLED:
        jobs.append(cron(tasks.cron_report_schedule,
                         **_cron_spec(settings.JOB_CRON_REPORT_SCHEDULE_SECONDS), unique=True))
    if settings.PILOT_MODE_ENABLED:
        jobs.append(cron(tasks.cron_customer_pilot_approval_reminders,
                         **_cron_spec(settings.JOB_CRON_CUSTOMER_PILOT_APPROVAL_REMINDERS_SECONDS),
                         unique=True))
    return jobs


async def _on_startup(ctx) -> None:
    # Credential decryption (discovery/monitoring) needs the master key, and the
    # schema must be migrated — fail fast like the API does.
    from app.security.secrets import ensure_master_key

    ensure_master_key()


async def _on_shutdown(ctx) -> None:  # pragma: no cover - lifecycle hook
    return None


class WorkerSettings:
    functions = ON_DEMAND_TASKS
    # Cron jobs run only on the default-queue worker (or dedicated scheduler) and
    # only when JOB_CRON_ENABLED — so periodic tasks are not registered by every
    # priority/processing worker. cron(unique=True) keeps them exactly-once even
    # if more than one process registers them.
    cron_jobs = (
        _build_cron_jobs()
        if (
            settings.JOB_CRON_ENABLED
            and (settings.JOB_WORKER_QUEUE or settings.JOB_QUEUE_NAME) == settings.JOB_QUEUE_NAME
        )
        else []
    )
    redis_settings = redis_settings()
    # The queue this worker drains. Deploy separate workers for high/low priority
    # by setting JOB_WORKER_QUEUE; the default worker drains the standard queue.
    queue_name = settings.JOB_WORKER_QUEUE or settings.JOB_QUEUE_NAME
    on_startup = _on_startup
    on_shutdown = _on_shutdown
    max_jobs = settings.JOB_MAX_CONCURRENCY
    job_timeout = settings.JOB_TIMEOUT_SECONDS
    keep_result = settings.JOB_KEEP_RESULT_SECONDS
    max_tries = settings.JOB_MAX_TRIES
    # Allow GET /jobs/{id}/cancel to abort an in-flight job via Arq.
    allow_abort_jobs = True
