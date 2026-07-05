"""Service layer for the async job queue (``app.models.job.Job``).

Owns all lifecycle transitions for job records and the enqueue path. The
enqueue path is queue-agnostic:

* When ``JOB_QUEUE_ENABLED`` is on and an Arq pool is available, work is
  enqueued to Redis and the API returns immediately with a QUEUED job.
* Otherwise the job runs **inline** (awaited in-request) so single-node
  deployments and the test suite keep working without a worker/Redis. The job
  record is still written, so the Job status API is consistent in both modes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.base import utcnow
from app.models.job import TERMINAL_STATUSES, Job, JobStatus, JobType

logger = logging.getLogger(__name__)


class JobService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------ reads
    async def get(self, job_id: str, organization_id: str | None = None) -> Job | None:
        job = await self.session.get(Job, job_id)
        if job is None:
            return None
        if organization_id is not None and job.organization_id != organization_id:
            return None
        return job

    async def list(
        self,
        organization_id: str | None,
        *,
        job_type: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Job]:
        stmt = select(Job)
        if organization_id is not None:
            stmt = stmt.where(Job.organization_id == organization_id)
        if job_type is not None:
            stmt = stmt.where(Job.job_type == job_type)
        if status is not None:
            stmt = stmt.where(Job.status == status)
        stmt = stmt.order_by(Job.created_at.desc()).offset(offset).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_dead_letter(
        self, organization_id: str | None, *, offset: int = 0, limit: int = 50
    ) -> list[Job]:
        return await self.list(
            organization_id, status=JobStatus.DEAD_LETTER.value, offset=offset, limit=limit
        )

    async def count(self, organization_id: str | None, *, status: str | None = None) -> int:
        stmt = select(func.count(Job.id))
        if organization_id is not None:
            stmt = stmt.where(Job.organization_id == organization_id)
        if status is not None:
            stmt = stmt.where(Job.status == status)
        return int((await self.session.execute(stmt)).scalar() or 0)

    # ----------------------------------------------------------------- writes
    async def create(
        self,
        *,
        job_type: JobType | str,
        organization_id: str | None,
        created_by: str | None,
        params: dict | None = None,
        max_attempts: int | None = None,
        priority: str = "default",
        timeout_seconds: int | None = None,
    ) -> Job:
        job = Job(
            job_type=job_type.value if isinstance(job_type, JobType) else str(job_type),
            organization_id=organization_id,
            created_by=created_by,
            params=params or {},
            status=JobStatus.QUEUED.value,
            max_attempts=max_attempts or settings.JOB_MAX_TRIES,
            priority=priority,
            timeout_seconds=timeout_seconds,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def set_arq_id(self, job: Job, arq_job_id: str | None) -> None:
        job.arq_job_id = arq_job_id
        await self.session.flush()

    async def mark_running(self, job: Job, *, attempt: int | None = None) -> None:
        job.status = JobStatus.RUNNING.value
        if attempt is not None:
            job.attempts = attempt
        else:
            job.attempts = (job.attempts or 0) + 1
        if job.started_at is None:
            job.started_at = utcnow()
        if job.progress < 1:
            job.progress = 1
        await self.session.commit()

    async def set_progress(self, job: Job, progress: int, message: str | None = None) -> None:
        job.progress = max(0, min(100, int(progress)))
        if message is not None:
            job.progress_message = message[:255]
        await self.session.commit()

    async def mark_completed(self, job: Job, result: dict | None = None) -> None:
        job.status = JobStatus.COMPLETED.value
        job.result = result
        job.progress = 100
        job.finished_at = utcnow()
        await self.session.commit()

    async def mark_retrying(self, job: Job, error: str) -> None:
        job.status = JobStatus.RETRYING.value
        job.error = error[:4000]
        await self.session.commit()

    async def mark_failed(self, job: Job, error: str, *, dead_letter: bool = False) -> None:
        job.status = JobStatus.DEAD_LETTER.value if dead_letter else JobStatus.FAILED.value
        job.error = error[:4000]
        job.finished_at = utcnow()
        await self.session.commit()

    async def mark_cancelled(self, job: Job) -> None:
        job.status = JobStatus.CANCELLED.value
        job.finished_at = utcnow()
        await self.session.commit()

    async def request_cancel(self, job: Job) -> bool:
        """Flag a job for cancellation. Returns False if already terminal."""
        if job.status in TERMINAL_STATUSES:
            return False
        job.cancel_requested = True
        # If it never started running we can mark it cancelled immediately.
        if job.status == JobStatus.QUEUED.value:
            job.status = JobStatus.CANCELLED.value
            job.finished_at = utcnow()
        await self.session.commit()
        return True

    async def reset_for_retry(self, job: Job) -> None:
        """Re-queue a FAILED / DEAD_LETTER job for another run."""
        job.status = JobStatus.QUEUED.value
        job.error = None
        job.progress = 0
        job.progress_message = None
        job.cancel_requested = False
        job.started_at = None
        job.finished_at = None
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = None
        await self.session.commit()

    # --------------------------------------------- leases + heartbeat (62B)
    async def acquire_lease(
        self, job: Job, owner: str, *, ttl_seconds: int | None = None
    ) -> bool:
        """Claim ownership of a run. Returns False if another live lease exists."""
        now = utcnow()
        ttl = ttl_seconds or settings.EXECUTION_LEASE_TTL_SECONDS
        if (
            job.lease_owner
            and job.lease_owner != owner
            and job.lease_expires_at is not None
            and job.lease_expires_at > now
        ):
            return False
        job.lease_owner = owner
        job.lease_expires_at = now + timedelta(seconds=ttl)
        job.heartbeat_at = now
        await self.session.commit()
        return True

    async def heartbeat(self, job: Job, owner: str, *, ttl_seconds: int | None = None) -> bool:
        """Extend a held lease. Returns False if the caller no longer owns it."""
        if job.lease_owner != owner:
            return False
        now = utcnow()
        ttl = ttl_seconds or settings.EXECUTION_LEASE_TTL_SECONDS
        job.heartbeat_at = now
        job.lease_expires_at = now + timedelta(seconds=ttl)
        await self.session.commit()
        return True

    async def release_lease(self, job: Job, owner: str | None = None) -> None:
        if owner is not None and job.lease_owner != owner:
            return
        job.lease_owner = None
        job.lease_expires_at = None
        await self.session.commit()

    async def list_stalled(self, *, now: datetime | None = None, limit: int = 200) -> list[Job]:
        """RUNNING jobs whose lease has expired (worker crashed / partitioned)."""
        now = now or utcnow()
        stmt = (
            select(Job)
            .where(
                Job.status == JobStatus.RUNNING.value,
                or_(Job.lease_expires_at.is_(None), Job.lease_expires_at < now),
            )
            .order_by(Job.started_at)
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())


def serialize_job(job: Job) -> dict:
    def _iso(value: datetime | None) -> str | None:
        return value.isoformat() if isinstance(value, datetime) else None

    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "organization_id": job.organization_id,
        "created_by": job.created_by,
        "arq_job_id": job.arq_job_id,
        "progress": job.progress,
        "progress_message": job.progress_message,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "cancel_requested": job.cancel_requested,
        "priority": getattr(job, "priority", "default"),
        "lease_owner": getattr(job, "lease_owner", None),
        "lease_expires_at": _iso(getattr(job, "lease_expires_at", None)),
        "heartbeat_at": _iso(getattr(job, "heartbeat_at", None)),
        "timeout_seconds": getattr(job, "timeout_seconds", None),
        "params": job.params or {},
        "result": job.result,
        "error": job.error,
        "created_at": _iso(job.created_at),
        "started_at": _iso(job.started_at),
        "finished_at": _iso(job.finished_at),
    }
