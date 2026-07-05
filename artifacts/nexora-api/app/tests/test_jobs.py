"""Tests for the async job queue (app.jobs / app.services.jobs / Job API).

Covers the JobService lifecycle, the execute_tracked wrapper (success,
cancellation, cooperative cancel via progress, dead-letter and retry), the Job
status API (list / get / cancel / retry / dead-letter, org isolation) and the
enqueue path with the queue enabled (202 + worker simulation).

The Arq worker/pool is never required: a FakePool stands in for Redis, and the
retry path that depends on ``arq`` is importorskip-guarded.
"""

import pytest

from app.core.config import settings
from app.database.session import AsyncSessionLocal
from app.jobs.runner import execute_tracked
from app.models.job import JobStatus, JobType
from app.services.jobs import JobService
from app.tests.conftest import auth_headers, create_authenticated_user, jwt_claims


# ------------------------------------------------------------------ helpers
async def _make_job(**kw) -> str:
    async with AsyncSessionLocal() as s:
        job = await JobService(s).create(
            job_type=kw.get("job_type", JobType.AI_TEAM_AGENT),
            organization_id=kw.get("organization_id"),
            created_by=kw.get("created_by"),
            params=kw.get("params"),
            max_attempts=kw.get("max_attempts"),
        )
        await s.commit()
        return job.id


async def _get_job(job_id: str):
    async with AsyncSessionLocal() as s:
        return await JobService(s).get(job_id)


class _FakeArqJob:
    def __init__(self, job_id: str):
        self.job_id = job_id


class FakePool:
    """Records enqueues without running anything (stands in for an Arq pool)."""

    def __init__(self):
        self.enqueued: list[tuple[str, dict]] = []

    async def enqueue_job(self, function: str, **kwargs):
        self.enqueued.append((function, kwargs))
        return _FakeArqJob(f"arq-{kwargs.get('job_id')}")


# =============================== JobService ================================
async def test_job_lifecycle_complete(setup_db):
    job_id = await _make_job(params={"a": 1})
    async with AsyncSessionLocal() as s:
        svc = JobService(s)
        job = await svc.get(job_id)
        assert job.status == JobStatus.QUEUED.value
        assert job.attempts == 0

        await svc.mark_running(job)
        assert job.status == JobStatus.RUNNING.value
        assert job.attempts == 1
        assert job.started_at is not None
        assert job.progress >= 1

        await svc.set_progress(job, 50, "halfway")
        assert job.progress == 50
        assert job.progress_message == "halfway"

        await svc.mark_completed(job, {"result": "ok"})
        assert job.status == JobStatus.COMPLETED.value
        assert job.progress == 100
        assert job.result == {"result": "ok"}
        assert job.finished_at is not None


async def test_job_dead_letter_and_listing(setup_db):
    job_id = await _make_job(job_type=JobType.UNIVERSAL_DISCOVERY)
    async with AsyncSessionLocal() as s:
        svc = JobService(s)
        job = await svc.get(job_id)
        await svc.mark_failed(job, "kaboom", dead_letter=True)
        assert job.status == JobStatus.DEAD_LETTER.value
        assert "kaboom" in job.error

        dlq = await svc.list_dead_letter(None)
        assert any(j.id == job_id for j in dlq)
        assert await svc.count(None, status=JobStatus.DEAD_LETTER.value) == 1


async def test_request_cancel_states(setup_db):
    # QUEUED -> cancel immediately marks CANCELLED.
    queued_id = await _make_job()
    async with AsyncSessionLocal() as s:
        svc = JobService(s)
        job = await svc.get(queued_id)
        assert await svc.request_cancel(job) is True
        assert job.status == JobStatus.CANCELLED.value

    # RUNNING -> cancel flags but keeps status until the task observes it.
    running_id = await _make_job()
    async with AsyncSessionLocal() as s:
        svc = JobService(s)
        job = await svc.get(running_id)
        await svc.mark_running(job)
        assert await svc.request_cancel(job) is True
        assert job.cancel_requested is True
        assert job.status == JobStatus.RUNNING.value

    # terminal -> cancel is a no-op.
    done_id = await _make_job()
    async with AsyncSessionLocal() as s:
        svc = JobService(s)
        job = await svc.get(done_id)
        await svc.mark_completed(job, {})
        assert await svc.request_cancel(job) is False


# ============================== execute_tracked ============================
async def test_execute_tracked_success(setup_db):
    job_id = await _make_job()
    ticks: list[int] = []

    async def executor(session, job, progress):
        await progress(40, "working")
        ticks.append(40)
        return {"ok": True}

    out = await execute_tracked({"job_try": 1}, job_id, executor)
    assert out["status"] == JobStatus.COMPLETED.value
    assert ticks == [40]
    job = await _get_job(job_id)
    assert job.status == JobStatus.COMPLETED.value
    assert job.progress == 100
    assert job.result == {"ok": True}
    assert job.attempts == 1
    assert job.started_at is not None and job.finished_at is not None


async def test_execute_tracked_precancelled_skips_executor(setup_db):
    job_id = await _make_job()
    async with AsyncSessionLocal() as s:
        svc = JobService(s)
        job = await svc.get(job_id)
        await svc.request_cancel(job)  # QUEUED -> CANCELLED

    ran = []

    async def executor(session, job, progress):
        ran.append(True)
        return {}

    out = await execute_tracked({"job_try": 1}, job_id, executor)
    assert out["status"] == JobStatus.CANCELLED.value
    assert ran == []


async def test_execute_tracked_cooperative_cancel(setup_db):
    job_id = await _make_job()
    reached_after_progress = []

    async def executor(session, job, progress):
        # A cancellation arrives mid-run; the next progress tick must abort.
        job.cancel_requested = True
        await session.commit()
        await progress(50, "midway")
        reached_after_progress.append(True)
        return {"ok": True}

    out = await execute_tracked({"job_try": 1}, job_id, executor)
    assert out["status"] == JobStatus.CANCELLED.value
    assert reached_after_progress == []
    job = await _get_job(job_id)
    assert job.status == JobStatus.CANCELLED.value


async def test_execute_tracked_inline_failure_dead_letters(setup_db):
    job_id = await _make_job(max_attempts=3)

    async def executor(session, job, progress):
        raise ValueError("boom")

    out = await execute_tracked({"job_try": 1, "inline": True}, job_id, executor)
    assert out["status"] == JobStatus.DEAD_LETTER.value
    assert "boom" in out["error"]
    job = await _get_job(job_id)
    assert job.status == JobStatus.DEAD_LETTER.value
    assert "ValueError" in job.error


async def test_execute_tracked_retry_then_dead_letter(setup_db):
    pytest.importorskip("arq")
    from arq.worker import Retry

    async def executor(session, job, progress):
        raise RuntimeError("transient")

    # Non-final attempt raises Retry and marks RETRYING.
    retry_id = await _make_job(max_attempts=3)
    with pytest.raises(Retry):
        await execute_tracked({"job_try": 1}, retry_id, executor)
    job = await _get_job(retry_id)
    assert job.status == JobStatus.RETRYING.value

    # Final attempt dead-letters (no further retry).
    final_id = await _make_job(max_attempts=3)
    out = await execute_tracked({"job_try": 3}, final_id, executor)
    assert out["status"] == JobStatus.DEAD_LETTER.value
    job = await _get_job(final_id)
    assert job.status == JobStatus.DEAD_LETTER.value


# ================================ Job API ==================================
async def _seed_job_for(token, **kw) -> str:
    claims = jwt_claims(token)
    org_id = claims.get("organization_id")
    user_id = claims.get("sub")
    return await _make_job(organization_id=org_id, created_by=user_id, **kw)


async def test_job_api_list_get_and_isolation(client):
    _, t1 = await create_authenticated_user(client, email="job1@e.com", username="jobu1")
    token1 = t1["access_token"]
    _, t2 = await create_authenticated_user(client, email="job2@e.com", username="jobu2")
    token2 = t2["access_token"]

    job_id = await _seed_job_for(token1, job_type=JobType.EXECUTIVE_REPORT)

    listed = await client.get("/v1/jobs", headers=auth_headers(token1))
    assert listed.status_code == 200, listed.text
    assert any(j["id"] == job_id for j in listed.json()["items"])

    got = await client.get(f"/v1/jobs/{job_id}", headers=auth_headers(token1))
    assert got.status_code == 200
    assert got.json()["job_type"] == JobType.EXECUTIVE_REPORT.value

    # Another org cannot see it.
    other = await client.get(f"/v1/jobs/{job_id}", headers=auth_headers(token2))
    assert other.status_code == 404


async def test_job_api_cancel(client):
    _, tokens = await create_authenticated_user(client, email="jobc@e.com", username="jobc")
    token = tokens["access_token"]
    job_id = await _seed_job_for(token)

    resp = await client.post(f"/v1/jobs/{job_id}/cancel", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == JobStatus.CANCELLED.value

    # Cancelling a terminal job conflicts.
    again = await client.post(f"/v1/jobs/{job_id}/cancel", headers=auth_headers(token))
    assert again.status_code == 409


async def test_job_api_dead_letter_listing(client):
    _, tokens = await create_authenticated_user(client, email="jobd@e.com", username="jobd")
    token = tokens["access_token"]
    job_id = await _seed_job_for(token, job_type=JobType.UNIVERSAL_DISCOVERY)
    async with AsyncSessionLocal() as s:
        svc = JobService(s)
        job = await svc.get(job_id)
        await svc.mark_failed(job, "dead", dead_letter=True)

    resp = await client.get("/v1/jobs/dead-letter", headers=auth_headers(token))
    assert resp.status_code == 200
    assert any(j["id"] == job_id for j in resp.json()["items"])


async def test_job_api_retry_reenqueues(client, monkeypatch):
    _, tokens = await create_authenticated_user(client, email="jobr@e.com", username="jobr")
    token = tokens["access_token"]
    claims = jwt_claims(token)
    params = {
        "organization_id": claims.get("organization_id"),
        "user_id": claims.get("sub"),
        "report_type": "weekly",
    }
    job_id = await _seed_job_for(token, job_type=JobType.EXECUTIVE_REPORT, params=params)
    async with AsyncSessionLocal() as s:
        svc = JobService(s)
        job = await svc.get(job_id)
        await svc.mark_failed(job, "dead", dead_letter=True)

    pool = FakePool()

    async def _get_pool():
        return pool

    monkeypatch.setattr("app.jobs.queue.get_arq_pool", _get_pool)

    resp = await client.post(f"/v1/jobs/{job_id}/retry", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == JobStatus.QUEUED.value
    assert body["arq_job_id"] == f"arq-{job_id}"
    assert pool.enqueued and pool.enqueued[0][0] == "run_executive_report"


async def test_enqueue_path_returns_202_and_worker_completes(client, monkeypatch):
    _, tokens = await create_authenticated_user(client, email="jobe@e.com", username="jobe")
    token = tokens["access_token"]

    pool = FakePool()

    async def _get_pool():
        return pool

    monkeypatch.setattr(settings, "JOB_QUEUE_ENABLED", True)
    monkeypatch.setattr("app.jobs.queue.get_arq_pool", _get_pool)

    # Trigger endpoint now enqueues instead of running synchronously.
    resp = await client.post("/v1/monitoring/poll", headers=auth_headers(token), json={})
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == JobStatus.QUEUED.value
    assert body["job_type"] == JobType.MONITORING_POLL.value
    job_id = body["id"]
    assert pool.enqueued and pool.enqueued[0][0] == "run_monitoring_poll"

    # The job is visible via the status API while queued.
    got = await client.get(f"/v1/jobs/{job_id}", headers=auth_headers(token))
    assert got.status_code == 200
    assert got.json()["status"] == JobStatus.QUEUED.value

    # Simulate the worker running the enqueued task out-of-band.
    from app.jobs.tasks import run_monitoring_poll

    _, kwargs = pool.enqueued[0]
    await run_monitoring_poll({"job_try": 1}, **kwargs)

    done = await client.get(f"/v1/jobs/{job_id}", headers=auth_headers(token))
    assert done.status_code == 200
    assert done.json()["status"] == JobStatus.COMPLETED.value
