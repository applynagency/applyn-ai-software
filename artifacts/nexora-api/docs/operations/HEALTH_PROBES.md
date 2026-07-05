# Health Probes (Kubernetes-grade)

Nexora exposes three probe endpoints designed for Kubernetes (and any
orchestrator that supports liveness/readiness/startup probes). All return
**structured JSON** and meaningful status codes.

| Endpoint     | Purpose    | Checks                                   | Codes |
| ------------ | ---------- | ---------------------------------------- | ----- |
| `GET /livez`    | Liveness   | none (process/event-loop only)           | `200` |
| `GET /readyz`   | Readiness  | Database, Redis, Scheduler, Storage, AI  | `200` (ok/degraded) / `503` (critical fail) |
| `GET /startupz` | Startup    | startup gate + Database                  | `200` (started) / `503` (starting) |

> The existing `GET {BASE_PATH}/health` endpoint (`/nexora-api/health`) is kept
> for backward compatibility. The new probes live at the **root** so probe
> configuration is independent of `BASE_PATH`.

## Semantics

### `/livez` — liveness
Returns `200 {"status": "alive", ...}` whenever the process is running and the
event loop can service the request. It performs **no dependency checks** on
purpose: a failing liveness probe causes Kubernetes to **restart** the pod, and
we never want a transient database/Redis hiccup to trigger restarts.

### `/readyz` — readiness
Runs all dependency checks concurrently and aggregates them:

- A failing **critical** check (**database**) → `503`, status `"fail"`. The pod
  is removed from the Service endpoints until it recovers.
- A failing/​warning **non-critical** check (redis / scheduler / storage / AI) →
  `200`, status `"degraded"`. The pod keeps serving — these dependencies degrade
  gracefully (rate limiting falls back to in-memory, AI falls back to
  deterministic responses, schedulers are background-only).
- All green → `200`, status `"ok"`.

### `/startupz` — startup
Returns `503 {"status": "starting"}` until the application lifespan has finished
initialization (DB tables created, master encryption key verified, schedulers
launched), then `200 {"status": "started"}` once startup is complete **and** the
database is reachable. Use this as a Kubernetes `startupProbe` so liveness and
readiness are held off during slow boots.

## Checks

| Check          | Critical | Verifies                                                        |
| -------------- | -------- | --------------------------------------------------------------- |
| `database`     | **yes**  | `SELECT 1` via the async session (time-boxed, 3s).              |
| `redis`        | no       | If `REDIS_URL` set: `PING` the rate-limit backend. Otherwise reports `warn` (in-memory rate limiting). |
| `scheduler`    | no       | Each **enabled** background loop (workflow / monitoring / escalation / discovery / universal-discovery) has a live task that has not crashed. |
| `storage`      | no       | Writes & deletes a probe file in the asset/`static` directory (falls back to the system temp dir). |
| `ai_providers` | no       | Whether Anthropic / OpenAI API keys are configured. **Config-only — no external network call** is made (probes must not incur billed/rate-limited requests). |

Each check is independently time-boxed and never raises; failures are reported
as structured results rather than crashing the probe.

## Response shape

```json
{
  "status": "degraded",
  "app": "Nexora AI Development Team",
  "version": "1.0.0",
  "uptime_seconds": 12.34,
  "checks": [
    {"name": "database", "status": "pass", "critical": true,  "detail": "reachable", "duration_ms": 2.38},
    {"name": "redis",    "status": "warn", "critical": false, "detail": "not configured (in-memory rate limiting)", "duration_ms": 0.0},
    {"name": "scheduler","status": "pass", "critical": false, "detail": "running=['workflow_scheduler'] disabled=[...]", "duration_ms": 0.0},
    {"name": "storage",  "status": "pass", "critical": false, "detail": "writable: /app/static", "duration_ms": 1.95},
    {"name": "ai_providers", "status": "pass", "critical": false, "detail": "anthropic=configured, openai=unconfigured", "duration_ms": 0.0}
  ]
}
```

`status` per check is one of `pass` | `warn` | `fail`; overall `status` is
`ok` | `degraded` | `fail`.

## Kubernetes configuration

```yaml
livenessProbe:
  httpGet: { path: /livez, port: 8000 }
  initialDelaySeconds: 0
  periodSeconds: 10
  failureThreshold: 3

readinessProbe:
  httpGet: { path: /readyz, port: 8000 }
  periodSeconds: 10
  failureThreshold: 3

startupProbe:
  httpGet: { path: /startupz, port: 8000 }
  periodSeconds: 5
  failureThreshold: 30   # allow up to ~150s for first boot
```

With a `startupProbe`, Kubernetes disables the liveness and readiness probes
until startup succeeds, preventing premature restarts during initialization.

## Files

| File                          | Change                                                       |
| ----------------------------- | ------------------------------------------------------------ |
| `app/core/health.py`          | New — probe state (startup gate, background task registry) and the Database/Redis/Scheduler/Storage/AI checks + aggregation. |
| `app/main.py`                 | New `/livez`, `/readyz`, `/startupz` routes; lifespan registers background tasks and flips the startup gate. |
| `app/security/rate_limit.py`  | Adds `ping()` to the rate-limit backends (used by the Redis check). |
| `app/tests/test_health.py`    | Unit tests (each check + aggregation + startup gate) and endpoint integration tests. |

## Notes

- **No external calls on the hot path.** Readiness/startup never call AI
  providers; the AI check is configuration-only. The database and Redis checks
  are local and time-boxed, so probes stay fast and cheap.
- **Degraded ≠ down.** Redis, scheduler, storage and AI are intentionally
  non-critical so a single degraded dependency does not take an otherwise
  healthy replica out of rotation.
