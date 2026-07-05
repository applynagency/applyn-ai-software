"""Async job status API.

* GET    /v1/jobs                 - list jobs (org-scoped; filter by type/status)
* GET    /v1/jobs/dead-letter     - jobs that exhausted retries (DLQ)
* GET    /v1/jobs/{job_id}        - job status / progress / result / error
* POST   /v1/jobs/{job_id}/cancel - request cancellation (aborts in-flight Arq job)
* POST   /v1/jobs/{job_id}/retry  - re-queue a FAILED / DEAD_LETTER job
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.jobs.tasks import TASK_REGISTRY
from app.models.job import TERMINAL_STATUSES, JobStatus
from app.schemas.job import JobListResponse, JobResponse
from app.services.jobs import JobService, serialize_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])

# JobType value -> Arq task name (on-demand tasks only).
_TYPE_TO_TASK = {jt.value: name for name, (_fn, jt) in TASK_REGISTRY.items()}


@router.get("", response_model=JobListResponse)
async def list_jobs(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    job_type: str | None = Query(default=None),
    job_status: str | None = Query(default=None, alias="status"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    org_id = org_context.requires_organization
    svc = JobService(session)
    rows = await svc.list(org_id, job_type=job_type, status=job_status, offset=offset, limit=limit)
    total = await svc.count(org_id, status=job_status)
    return JobListResponse(
        items=[JobResponse(**serialize_job(r)) for r in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/dead-letter", response_model=JobListResponse)
async def list_dead_letter(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    org_id = org_context.requires_organization
    svc = JobService(session)
    rows = await svc.list_dead_letter(org_id, offset=offset, limit=limit)
    total = await svc.count(org_id, status=JobStatus.DEAD_LETTER.value)
    return JobListResponse(
        items=[JobResponse(**serialize_job(r)) for r in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    org_id = org_context.requires_organization
    job = await JobService(session).get(job_id, organization_id=org_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobResponse(**serialize_job(job))


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    org_id = org_context.requires_organization
    svc = JobService(session)
    job = await svc.get(job_id, organization_id=org_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job already terminal ({job.status})",
        )
    arq_job_id = job.arq_job_id
    await svc.request_cancel(job)
    # Best-effort abort of an in-flight Arq job.
    if arq_job_id:
        try:
            from app.jobs.queue import get_arq_pool

            pool = await get_arq_pool()
            if pool is not None:
                from arq.jobs import Job as ArqJob

                await ArqJob(arq_job_id, pool).abort(timeout=0)
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("job_abort_failed", extra={"job_id": job_id, "error": str(exc)})
    await session.refresh(job)
    return JobResponse(**serialize_job(job))


@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(
    job_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    org_id = org_context.requires_organization
    svc = JobService(session)
    job = await svc.get(job_id, organization_id=org_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status not in (JobStatus.FAILED.value, JobStatus.DEAD_LETTER.value,
                          JobStatus.CANCELLED.value):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed, dead-letter or cancelled jobs can be retried",
        )
    task_name = _TYPE_TO_TASK.get(job.job_type)
    if task_name is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job type {job.job_type} is not retriable",
        )

    await svc.reset_for_retry(job)
    task_kwargs = dict(job.params or {})

    from app.jobs.queue import get_arq_pool

    pool = await get_arq_pool()
    if pool is not None:
        arq_job = await pool.enqueue_job(task_name, job_id=job.id, **task_kwargs)
        if arq_job is not None:
            await svc.set_arq_id(job, arq_job.job_id)
            await session.commit()
    else:
        fn = TASK_REGISTRY[task_name][0]
        await fn({"job_try": 1, "inline": True}, job_id=job.id, **task_kwargs)
        await session.refresh(job)
    return JobResponse(**serialize_job(job))
