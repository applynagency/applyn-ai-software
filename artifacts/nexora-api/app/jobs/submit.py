"""Enqueue helper used by the trigger endpoints.

Creates a durable ``Job`` row, then either enqueues it onto Arq (returns
immediately) or — if the queue is enabled but no Redis pool is available —
runs it inline as a safety net. Always commits the job row first so a separate
worker process can load it.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.jobs import queue as _queue
from app.models.job import Job, JobType
from app.services.jobs import JobService

logger = logging.getLogger(__name__)

# Priority -> Arq queue name. Deploy one worker per queue (or a single worker on
# the default queue) — higher-priority workers drain their queue first.
PRIORITY_HIGH = "high"
PRIORITY_DEFAULT = "default"
PRIORITY_LOW = "low"


def queue_for_priority(priority: str) -> str:
    if priority == PRIORITY_HIGH:
        return settings.JOB_QUEUE_NAME_HIGH
    if priority == PRIORITY_LOW:
        return settings.JOB_QUEUE_NAME_LOW
    return settings.JOB_QUEUE_NAME


def accepted_response(job: Job):
    """Build a 202 Accepted response carrying the job record."""
    from fastapi.responses import JSONResponse

    from app.services.jobs import serialize_job

    status_code = 200 if job.status in ("COMPLETED", "FAILED", "DEAD_LETTER", "CANCELLED") else 202
    return JSONResponse(status_code=status_code, content=serialize_job(job))


async def submit_job(
    session: AsyncSession,
    *,
    task_name: str,
    job_type: JobType,
    organization_id: str | None,
    user_id: str | None,
    params: dict | None = None,
    task_kwargs: dict | None = None,
    priority: str = PRIORITY_DEFAULT,
    delay_seconds: float | None = None,
    run_at: datetime | None = None,
) -> Job:
    svc = JobService(session)
    job = await svc.create(
        job_type=job_type,
        organization_id=organization_id,
        created_by=user_id,
        params=params or {},
        priority=priority,
    )
    await session.commit()

    task_kwargs = task_kwargs or {}
    # Arq consumes these ``_``-prefixed control kwargs itself (they are not passed
    # to the task). Only set a queue when routing off the default so existing
    # default-priority enqueues are byte-for-byte unchanged.
    enqueue_opts: dict = {}
    queue_name = queue_for_priority(priority)
    if queue_name != settings.JOB_QUEUE_NAME:
        enqueue_opts["_queue_name"] = queue_name
    if run_at is not None:
        enqueue_opts["_defer_until"] = run_at
    elif delay_seconds is not None and delay_seconds > 0:
        enqueue_opts["_defer_by"] = delay_seconds

    # Resolve via the module (not a bound name) so monkeypatching
    # ``app.jobs.queue.get_arq_pool`` always reaches this call site regardless
    # of import order — keeps the enqueue tests order-independent.
    pool = await _queue.get_arq_pool()
    if pool is not None:
        arq_job = await pool.enqueue_job(
            task_name, job_id=job.id, **task_kwargs, **enqueue_opts
        )
        if arq_job is not None:
            await svc.set_arq_id(job, arq_job.job_id)
            await session.commit()
        logger.info(
            "job_enqueued",
            extra={
                "job_id": job.id,
                "task": task_name,
                "priority": priority,
                "deferred": bool(run_at or delay_seconds),
            },
        )
        return job

    # Queue enabled but no usable pool — run inline so work is not silently lost.
    logger.warning("job_inline_fallback", extra={"job_id": job.id, "task": task_name})
    from app.jobs.tasks import TASK_REGISTRY

    fn = TASK_REGISTRY[task_name][0]
    await fn({"job_try": 1, "inline": True}, job_id=job.id, **task_kwargs)
    await session.refresh(job)
    return job
