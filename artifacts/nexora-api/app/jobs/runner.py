"""Shared job execution machinery used by every Arq task.

``execute_tracked`` wraps an *executor* coroutine with the full job lifecycle:
RUNNING → COMPLETED, with cooperative cancellation, progress reporting, retry
accounting and a dead-letter terminal state once retries are exhausted. It is
used identically by the Arq worker and by the inline fallback (``app.jobs.submit``).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import AsyncSessionLocal
from app.models.job import JobStatus
from app.services.jobs import JobService

logger = logging.getLogger(__name__)

# executor(session, job, progress) -> result dict
Executor = Callable[[AsyncSession, Any, "ProgressFn"], Awaitable[dict | None]]
ProgressFn = Callable[..., Awaitable[None]]


class JobCancelled(Exception):
    """Raised by an executor (or the wrapper) to stop a job without retrying."""


async def _load_actor(session: AsyncSession, user_id: str | None, organization_id: str | None):
    """Reconstruct ``(User, OrgContext)`` for an org-scoped service call."""
    from app.auth.org_context import OrgContext
    from app.models.organization import OrganizationRole
    from app.models.user import User

    if not user_id:
        return None
    user = await session.get(User, user_id)
    if user is None:
        return None
    role = None
    if organization_id:
        if user.is_superuser:
            role = OrganizationRole.OWNER
        else:
            from app.repositories.organization import OrganizationMemberRepository

            membership = await OrganizationMemberRepository(session).get_membership(
                organization_id, user_id
            )
            role = membership.role if membership else None
    return user, OrgContext(user=user, organization_id=organization_id, role=role)


async def owner_actor(session: AsyncSession, organization_id: str):
    """Resolve the org OWNER as the acting principal for system-driven jobs."""
    from sqlalchemy import select

    from app.auth.org_context import OrgContext
    from app.models.organization import OrganizationMember, OrganizationRole
    from app.models.user import User

    stmt = (
        select(OrganizationMember)
        .where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.role == OrganizationRole.OWNER,
        )
        .order_by(OrganizationMember.created_at.asc())
        .limit(1)
    )
    member = (await session.execute(stmt)).scalar_one_or_none()
    if member is None:
        return None
    user = await session.get(User, member.user_id)
    if user is None:
        return None
    return user, OrgContext(user=user, organization_id=organization_id, role=OrganizationRole.OWNER)


def _retry_delay(attempt: int) -> float:
    base = max(0.0, settings.JOB_RETRY_BASE_DELAY_SECONDS)
    return base * (2 ** max(0, attempt - 1))


async def execute_tracked(ctx: dict, job_id: str, executor: Executor) -> dict:
    """Run ``executor`` for ``job_id`` with full lifecycle tracking.

    Honors Arq's retry contract: on a non-final attempt it raises ``Retry`` so
    Arq re-runs the task with backoff; on the final attempt it records a
    dead-letter and returns (the Job table is the durable source of truth).
    """
    attempt = int(ctx.get("job_try", 1))
    started = time.perf_counter()

    def _metric(status: str) -> None:
        try:
            from app.observability import metrics

            metrics.record_job(
                job_type, status, seconds=time.perf_counter() - started
            )
        except Exception:  # pragma: no cover - metrics optional
            pass

    async with AsyncSessionLocal() as session:
        svc = JobService(session)
        job = await svc.get(job_id)
        if job is None:
            logger.warning("job_missing", extra={"job_id": job_id})
            return {"status": "missing", "job_id": job_id}
        job_type = job.job_type

        if job.cancel_requested or job.status == JobStatus.CANCELLED.value:
            await svc.mark_cancelled(job)
            _metric(JobStatus.CANCELLED.value)
            return {"status": JobStatus.CANCELLED.value, "job_id": job_id}

        await svc.mark_running(job, attempt=attempt)

        async def progress(pct: int, message: str | None = None) -> None:
            # Re-read the cancel flag cooperatively on every progress tick.
            await session.refresh(job, ["cancel_requested"])
            if job.cancel_requested:
                raise JobCancelled()
            await svc.set_progress(job, pct, message)

        try:
            result = await executor(session, job, progress)
        except JobCancelled:
            await session.rollback()
            await svc.mark_cancelled(job)
            _metric(JobStatus.CANCELLED.value)
            return {"status": JobStatus.CANCELLED.value, "job_id": job_id}
        except Exception as exc:  # noqa: BLE001 - lifecycle boundary
            await session.rollback()
            error = f"{type(exc).__name__}: {exc}"
            is_final = attempt >= (job.max_attempts or settings.JOB_MAX_TRIES)
            if is_final:
                await svc.mark_failed(job, error, dead_letter=True)
                _metric(JobStatus.DEAD_LETTER.value)
                logger.error("job_dead_letter", extra={"job_id": job_id, "error": error})
                return {"status": JobStatus.DEAD_LETTER.value, "job_id": job_id, "error": error}
            await svc.mark_retrying(job, error)
            _metric(JobStatus.RETRYING.value)
            logger.warning(
                "job_retry", extra={"job_id": job_id, "attempt": attempt, "error": error}
            )
            if ctx.get("inline"):
                # No Arq scheduler in inline mode — surface the failure as final.
                await svc.mark_failed(job, error, dead_letter=True)
                return {"status": JobStatus.DEAD_LETTER.value, "job_id": job_id, "error": error}
            from arq.worker import Retry

            raise Retry(defer=_retry_delay(attempt)) from exc

        await svc.mark_completed(job, result if isinstance(result, dict) else None)
        _metric(JobStatus.COMPLETED.value)
        return {"status": JobStatus.COMPLETED.value, "job_id": job_id}
