"""Unified execution engine (Sprint 62A).

ONE runtime for everything that "runs": AI jobs, workflows, agent runs and
scheduled jobs. It is a thin convergence facade over the existing durable job
machinery (``app/jobs``) — adding first-class checkpoints, approvals, cancel,
retry and resume on top of a single ``jobs`` table, so there is exactly one
execution engine rather than several bespoke runners.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.base import utcnow
from app.models.job import TERMINAL_STATUSES, Job, JobStatus, JobType
from app.models.platform_core import ExecutionCheckpoint
from app.services.jobs import JobService, serialize_job


class ExecutionError(Exception):
    pass


class ExecutionEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.jobs = JobService(session)

    # -------------------------------------------------------------- submit
    async def submit(
        self,
        *,
        task_name: str,
        job_type: JobType | str,
        organization_id: str | None,
        user_id: str | None,
        params: dict | None = None,
        task_kwargs: dict | None = None,
        priority: str = "default",
        delay_seconds: float | None = None,
        run_at: datetime | None = None,
    ) -> dict:
        from app.jobs.submit import submit_job

        jt = job_type if isinstance(job_type, JobType) else JobType(str(job_type))
        job = await submit_job(
            self.session, task_name=task_name, job_type=jt,
            organization_id=organization_id, user_id=user_id, params=params,
            task_kwargs=task_kwargs, priority=priority, delay_seconds=delay_seconds,
            run_at=run_at)
        return serialize_job(job)

    # -------------------------------------------------------------- status
    async def get(self, run_id: str, *, organization_id: str | None = None) -> dict | None:
        job = await self.jobs.get(run_id, organization_id)
        return serialize_job(job) if job else None

    async def cancel(self, run_id: str, *, organization_id: str | None = None) -> bool:
        job = await self.jobs.get(run_id, organization_id)
        if job is None:
            raise ExecutionError("run not found")
        return await self.jobs.request_cancel(job)

    async def retry(self, run_id: str, *, organization_id: str | None = None) -> dict:
        job = await self.jobs.get(run_id, organization_id)
        if job is None:
            raise ExecutionError("run not found")
        await self.jobs.reset_for_retry(job)
        return serialize_job(job)

    # -------------------------------------------------------------- checkpoints
    async def checkpoint(
        self, run_id: str, *, label: str | None = None, state: dict | None = None,
        organization_id: str | None = None,
    ) -> ExecutionCheckpoint:
        existing = (await self.session.execute(
            select(ExecutionCheckpoint).where(ExecutionCheckpoint.job_id == run_id)
            .order_by(ExecutionCheckpoint.sequence.desc()).limit(1)
        )).scalar_one_or_none()
        seq = (existing.sequence + 1) if existing else 0
        cp = ExecutionCheckpoint(job_id=run_id, organization_id=organization_id,
                                 sequence=seq, label=label, state=state or {})
        self.session.add(cp)
        await self.session.flush()
        return cp

    async def list_checkpoints(self, run_id: str) -> list[ExecutionCheckpoint]:
        return list((await self.session.execute(
            select(ExecutionCheckpoint).where(ExecutionCheckpoint.job_id == run_id)
            .order_by(ExecutionCheckpoint.sequence))).scalars().all())

    async def latest_checkpoint(self, run_id: str) -> ExecutionCheckpoint | None:
        return (await self.session.execute(
            select(ExecutionCheckpoint).where(ExecutionCheckpoint.job_id == run_id)
            .order_by(ExecutionCheckpoint.sequence.desc()).limit(1))).scalar_one_or_none()

    # -------------------------------------------------------------- approvals
    async def approve(self, run_id: str, *, approver_id: str | None = None,
                      organization_id: str | None = None) -> dict:
        job = await self.jobs.get(run_id, organization_id)
        if job is None:
            raise ExecutionError("run not found")
        await self.checkpoint(run_id, label="approved",
                              state={"approved_by": approver_id},
                              organization_id=organization_id)
        # Re-queue an approval-gated run so it can continue.
        if job.status in (JobStatus.FAILED.value, JobStatus.DEAD_LETTER.value,
                          JobStatus.CANCELLED.value):
            await self.jobs.reset_for_retry(job)
        return serialize_job(job)

    async def resume(self, run_id: str, *, organization_id: str | None = None) -> dict:
        job = await self.jobs.get(run_id, organization_id)
        if job is None:
            raise ExecutionError("run not found")
        cp = await self.latest_checkpoint(run_id)
        params = dict(job.params or {})
        if cp is not None:
            params["_resume_state"] = cp.state
            params["_resume_sequence"] = cp.sequence
        job.params = params
        await self.jobs.reset_for_retry(job)
        return serialize_job(job)

    # ----------------------------------------------- leases + heartbeat (62B)
    async def claim(self, run_id: str, owner: str, *, ttl_seconds: int | None = None) -> bool:
        job = await self.jobs.get(run_id)
        if job is None:
            raise ExecutionError("run not found")
        return await self.jobs.acquire_lease(job, owner, ttl_seconds=ttl_seconds)

    async def heartbeat(self, run_id: str, owner: str, *, ttl_seconds: int | None = None) -> bool:
        job = await self.jobs.get(run_id)
        if job is None:
            raise ExecutionError("run not found")
        return await self.jobs.heartbeat(job, owner, ttl_seconds=ttl_seconds)

    # ----------------------------------------------- recovery + cleanup (62B)
    async def recover_stalled(self, *, now: datetime | None = None) -> dict:
        """Recover runs whose lease expired or that exceeded their timeout.

        * a stalled run with retries left → re-queued (reset for retry)
        * a stalled run with no retries left → dead-lettered (poison guard)
        * a run past its wall-clock timeout → failed/retried as above

        Idempotent; intended to be driven by a single recovery cron. Returns a
        small summary so the cron result is observable.
        """
        now = now or utcnow()
        default_timeout = int(settings.EXECUTION_DEFAULT_TIMEOUT_SECONDS)
        requeued = dead_lettered = timed_out = 0

        stalled = await self.jobs.list_stalled(now=now)
        for job in stalled:
            # Distinguish a true timeout (ran too long) from a lost lease.
            limit = job.timeout_seconds or default_timeout
            is_timeout = bool(
                job.started_at is not None
                and limit
                and (now - job.started_at) >= timedelta(seconds=limit)
            )
            if is_timeout:
                timed_out += 1
            if (job.attempts or 0) >= (job.max_attempts or 1):
                await self.jobs.mark_failed(
                    job,
                    "execution timed out" if is_timeout else "execution stalled (lease expired)",
                    dead_letter=True,
                )
                dead_lettered += 1
                _metric_recovered("dead_lettered")
            else:
                await self.jobs.reset_for_retry(job)
                requeued += 1
                _metric_recovered("requeued")
        return {
            "checked": len(stalled),
            "requeued": requeued,
            "dead_lettered": dead_lettered,
            "timed_out": timed_out,
        }

    async def cleanup_dead(self, *, retention_days: int | None = None,
                           now: datetime | None = None) -> int:
        """Delete terminal runs older than the retention window (bounded growth)."""
        now = now or utcnow()
        days = retention_days if retention_days is not None else settings.EXECUTION_DEAD_RETENTION_DAYS
        if not days:
            return 0
        cutoff = now - timedelta(days=days)
        stmt = select(Job).where(
            Job.status.in_(tuple(TERMINAL_STATUSES)),
            Job.finished_at.is_not(None),
            Job.finished_at < cutoff,
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        for job in rows:
            await self.session.delete(job)
        if rows:
            await self.session.commit()
            for _ in rows:
                _metric_recovered("cleaned")
        return len(rows)

    async def analytics(self, *, organization_id: str | None = None) -> dict:
        """Execution KPIs: counts by status, active leases, avg duration."""
        stmt = select(Job.status, func.count(Job.id))
        if organization_id is not None:
            stmt = stmt.where(Job.organization_id == organization_id)
        stmt = stmt.group_by(Job.status)
        by_status = {str(s): int(n) for s, n in (await self.session.execute(stmt)).all()}

        now = utcnow()
        active_stmt = select(func.count(Job.id)).where(
            Job.status == JobStatus.RUNNING.value,
            Job.lease_expires_at.is_not(None),
            Job.lease_expires_at > now,
        )
        if organization_id is not None:
            active_stmt = active_stmt.where(Job.organization_id == organization_id)
        active = int((await self.session.execute(active_stmt)).scalar() or 0)
        try:
            from app.observability import metrics

            metrics.set_execution_active(active)
        except Exception:  # pragma: no cover
            pass
        return {
            "organization_id": organization_id,
            "by_status": by_status,
            "active_leases": active,
            "total": sum(by_status.values()),
        }


def _metric_recovered(action: str) -> None:
    try:
        from app.observability import metrics

        metrics.record_execution_recovered(action)
    except Exception:  # pragma: no cover
        pass
