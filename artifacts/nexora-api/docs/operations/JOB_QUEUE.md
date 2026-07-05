# Async Job Queue (Arq + Redis)

Nexora can run its long-running work — **AI Team agents, AI Team workflows,
Infrastructure & Universal Discovery, Monitoring polls, and Report generation**
— as out-of-request background jobs on an [Arq](https://arq-docs.helpmanual.io/)
(Redis-backed) task queue instead of blocking the HTTP request until the LLM
call / cloud scan / aggregation completes.

The system is **opt-in** and backward compatible:

| `JOB_QUEUE_ENABLED` | Trigger endpoints | Periodic work |
| --- | --- | --- |
| `false` (default) | Run **synchronously** in-request, same response as before | In-process `asyncio` scheduler loops (unchanged) |
| `true` | **Enqueue** a job and return `202 Accepted` + a job id | Arq worker **cron jobs** (the in-process loops are not started) |

This means single-node deployments and the test suite keep working untouched,
while production can flip one flag (plus run a worker) to offload everything.

---

## Architecture

```
HTTP trigger (POST /ai-team-workflows/{id}/execute, /discovery/sync, …)
        │  JOB_QUEUE_ENABLED=true
        ▼
   submit_job()  ── creates a durable Job row (status=QUEUED) ──► Postgres
        │
        ▼  enqueue_job(task, job_id=…)
   Arq pool (Redis)
        │
        ▼
   Arq worker  (arq app.jobs.worker.WorkerSettings)
        │
        ▼
   task fn ──► execute_tracked(ctx, job_id, executor)
                  ├─ mark RUNNING (attempt = job_try)
                  ├─ progress(pct, msg)  + cooperative cancel check
                  ├─ call existing service (AITeamWorkflowService, …)
                  ├─ success → mark COMPLETED (+ result JSON)
                  ├─ failure & retries left → mark RETRYING, raise arq Retry (backoff)
                  └─ failure & retries exhausted → mark DEAD_LETTER
```

Key modules:

| File | Responsibility |
| --- | --- |
| `app/models/job.py` | `Job` table + `JobType` / `JobStatus` enums |
| `app/services/jobs.py` | `JobService` lifecycle transitions + `serialize_job` |
| `app/jobs/queue.py` | Lazy Arq Redis pool (`get_arq_pool` / `close_arq_pool`) |
| `app/jobs/runner.py` | `execute_tracked` wrapper (status/progress/retry/DLQ/cancel) + actor loaders |
| `app/jobs/tasks.py` | One task per subsystem + cron tasks + `TASK_REGISTRY` |
| `app/jobs/submit.py` | `submit_job` (enqueue or inline) + `accepted_response` |
| `app/jobs/worker.py` | `WorkerSettings` — the `arq` entrypoint |
| `app/api/v1/jobs.py` | Job status API (`/v1/jobs/*`) |

All `arq` imports are **lazy** — the API process boots and the test suite runs
without `arq` installed. Only the worker process strictly requires it.

---

## Running the worker

```bash
# 1. Point the queue at Redis (defaults to REDIS_URL when JOB_QUEUE_REDIS_URL is unset)
export JOB_QUEUE_ENABLED=true
export REDIS_URL=redis://redis:6379/0
export MASTER_ENCRYPTION_KEY=...        # needed to decrypt integration credentials
export DATABASE_URL=postgresql+asyncpg://...

# 2. Start the API as usual (it will enqueue instead of running inline)
uvicorn app.main:app

# 3. Start one or more workers
arq app.jobs.worker.WorkerSettings
```

The worker also runs the **periodic cron jobs** that replace the in-process
loops (each still respects its subsystem `*_ENABLED` flag):

| Cron task | Replaces | Cadence setting |
| --- | --- | --- |
| `cron_workflow_schedules` | `workflow_scheduler_loop` | `JOB_CRON_WORKFLOW_SECONDS` |
| `cron_monitoring` | `monitoring_loop` | `JOB_CRON_MONITORING_SECONDS` |
| `cron_escalation` | `escalation_loop` | `JOB_CRON_ESCALATION_SECONDS` |
| `cron_universal_discovery` | `universal_discovery_loop` | `JOB_CRON_UNIVERSAL_DISCOVERY_SECONDS` |

> The API's `/readyz` scheduler check reports `delegated to async job queue worker`
> when `JOB_QUEUE_ENABLED=true`, since the loops no longer live in the API process.

---

## Configuration

All settings live on `app/core/config.py`:

| Setting | Default | Meaning |
| --- | --- | --- |
| `JOB_QUEUE_ENABLED` | `false` | Master switch (enqueue vs. synchronous). |
| `JOB_QUEUE_REDIS_URL` | `None` | Queue Redis DSN; falls back to `REDIS_URL`. |
| `JOB_QUEUE_NAME` | `nexora:jobs` | Logical queue name. |
| `JOB_MAX_TRIES` | `3` | Total attempts per job before dead-letter. |
| `JOB_RETRY_BASE_DELAY_SECONDS` | `5.0` | Exponential backoff base (`base * 2^(attempt-1)`). |
| `JOB_TIMEOUT_SECONDS` | `900` | Hard per-job timeout. |
| `JOB_KEEP_RESULT_SECONDS` | `3600` | How long Arq keeps a result in Redis. |
| `JOB_MAX_CONCURRENCY` | `10` | Max jobs running per worker. |
| `JOB_CRON_*_SECONDS` | varies | Cron cadences (see table above). |

---

## Job status API

All routes are organization-scoped and audited; cross-org access returns `404`.

| Method & path | Description |
| --- | --- |
| `GET /v1/jobs` | List jobs (filters: `?job_type=`, `?status=`, `?offset=`, `?limit=`). |
| `GET /v1/jobs/dead-letter` | List dead-letter jobs (retries exhausted). |
| `GET /v1/jobs/{job_id}` | Status, progress, result, error, attempts. |
| `POST /v1/jobs/{job_id}/cancel` | Request cancellation (aborts an in-flight Arq job). |
| `POST /v1/jobs/{job_id}/retry` | Re-queue a `FAILED` / `DEAD_LETTER` / `CANCELLED` job. |

### Job lifecycle (`JobStatus`)

```
QUEUED ─► RUNNING ─► COMPLETED
            │  ├─► RETRYING ─► RUNNING (next attempt)
            │  └─► DEAD_LETTER         (retries exhausted)
            └─► CANCELLED              (cooperative cancel)
QUEUED ─► CANCELLED                    (cancel before it starts)
```

### Example

```bash
# Enqueue an executive report (queue enabled)
curl -XPOST .../v1/executive-reports/generate -d '{"report_type":"weekly"}'
# → 202 { "id": "…", "status": "QUEUED", "job_type": "EXECUTIVE_REPORT", … }

# Poll status
curl .../v1/jobs/<id>
# → 200 { "status": "RUNNING", "progress": 30, "progress_message": "aggregating metrics" }
# … eventually { "status": "COMPLETED", "progress": 100, "result": { … } }
```

---

## Features

- **Job status API** — durable `Job` rows are the source of truth (independent of
  Redis result retention), exposing status, progress (0–100 + message), attempts,
  result and error.
- **Retry** — Arq retries up to `JOB_MAX_TRIES` with exponential backoff; each
  attempt updates `attempts` and flips the job to `RETRYING` between tries.
- **Dead-letter queue** — once retries are exhausted the job becomes
  `DEAD_LETTER` (queryable at `GET /v1/jobs/dead-letter`) and can be re-queued
  via `POST /v1/jobs/{id}/retry`.
- **Cancellation** — two layers: (1) `cancel_requested` is observed cooperatively
  on every `progress()` tick and aborts the task with `CANCELLED`; (2) an
  in-flight Arq job is also `abort()`-ed (the worker runs with
  `allow_abort_jobs = True`). Jobs cancelled before they start are marked
  `CANCELLED` immediately.
- **Progress updates** — tasks report coarse milestones (queued → running →
  domain milestones → completed); discovery/monitoring also persist their own
  fine-grained progress on their existing scan/poll rows.

---

## Tests

`app/tests/test_jobs.py` covers:

- `JobService` lifecycle (create/run/progress/complete/fail/dead-letter/cancel/retry, list/count, org isolation).
- `execute_tracked`: success, pre-cancellation, cooperative cancel via `progress()`,
  inline dead-letter, and (when `arq` is installed) the retry → `Retry` and
  final-attempt dead-letter paths.
- Job status API: list / get / cancel (+ `409` on terminal) / dead-letter listing /
  retry re-enqueue, with a `FakePool` standing in for Redis.
- The enqueue path: with the queue enabled, a trigger endpoint returns `202` +
  a `QUEUED` job, and a simulated worker run drives it to `COMPLETED`.

Run them (install `arq` first to exercise the retry path):

```bash
pip install 'arq>=0.26.0'
pytest app/tests/test_jobs.py -q
```

---

## Migration

The `jobs` table ships as Alembic migration `0002_jobs` (on top of the squashed
`0001_baseline`). It creates the table directly from the ORM model with
`checkfirst=True`, so it is idempotent whether or not the squashed baseline
(which derives from live ORM metadata) already created it.

```bash
alembic upgrade head            # applies 0001_baseline → 0002_jobs
python -m app.database.migration_check
alembic check                   # no drift
```
