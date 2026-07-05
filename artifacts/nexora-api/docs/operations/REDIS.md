# Redis Integration

Nexora uses a single Redis deployment as shared infrastructure for several
subsystems. Every feature is **optional at runtime**: when `REDIS_URL` is not
set (or the `redis` package / server is unavailable) each feature transparently
falls back to an equivalent in-process implementation, so the API boots and the
full test suite runs without Redis. Distributed behaviour (shared across API
replicas) only kicks in once Redis is configured.

```
REDIS_URL=redis://localhost:6379/0
```

## Subsystems

| Feature              | Module                          | Redis structure                         | Fallback (no Redis)            |
| -------------------- | ------------------------------- | --------------------------------------- | ------------------------------ |
| Shared client        | `app/redis/client.py`           | one `redis.asyncio` pool                | `None` → features fall back    |
| Cache                | `app/redis/cache.py`            | `nexora:cache:*` (string + TTL)         | process-local TTL dict         |
| Session store        | `app/redis/sessions.py`         | `nexora:session:<jti>` + `nexora:sessions:<user>` set | process-local dict |
| JWT denylist         | `app/redis/denylist.py`         | `nexora:denylist:<jti>` (TTL)           | process-local dict             |
| Distributed locks    | `app/redis/locks.py`            | `nexora:lock:<name>` (`SET NX PX`)      | process-local token map        |
| Notification queue   | `app/redis/notifications.py`    | `nexora:notifications:queue` (list)     | process-local deque            |
| Rate limiting        | `app/security/rate_limit.py`    | sorted-set sliding window (Lua)         | in-process sliding window      |
| Background jobs      | `app/jobs/` (Arq)               | Arq queue + results                     | inline / in-process schedulers |

All keys are namespaced under `REDIS_KEY_PREFIX` (default `nexora`).

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `REDIS_URL` | _unset_ | DSN for the shared client (and rate-limit / Arq fallback). |
| `REDIS_KEY_PREFIX` | `nexora` | Namespace for every key. |
| `REDIS_MAX_CONNECTIONS` | `50` | Connection-pool ceiling. |
| `CACHE_ENABLED` | `true` | Toggle the application cache. |
| `CACHE_DEFAULT_TTL_SECONDS` | `300` | Default TTL when `set`/`get_or_set` omit one. |
| `SESSION_STORE_ENABLED` | `true` | Record/list/revoke server-side sessions. |
| `JWT_DENYLIST_ENABLED` | `true` | Enforce access-token revocation on every request. |
| `DISTRIBUTED_LOCK_ENABLED` | `true` | Enable lock acquisition (off = always "acquired"). |
| `SCHEDULER_LOCK_TTL_SECONDS` | `300` | TTL for each scheduler tick lock. |
| `NOTIFICATION_QUEUE_ENABLED` | `false` | Buffer outbound notifications instead of inline send. |
| `NOTIFICATION_QUEUE_POLL_SECONDS` | `5` | Drainer poll cadence. |
| `NOTIFICATION_QUEUE_MAX_ATTEMPTS` | `5` | Delivery attempts before a payload is dropped. |

## Cache

```python
from app.redis import cache

# get_or_set computes + caches on a miss (sync or async factory).
catalog = await cache.get_or_set("integrations:catalog", 300, load_catalog)

await cache.set("key", {"a": 1}, ttl=60)
value = await cache.get("key")          # -> {"a": 1}
await cache.incr("hits", 1, ttl=3600)   # atomic counter
await cache.delete("key")
```

Hits/misses are exported as `nexora_cache_events_total{event="hit|miss"}`.

## Sessions & JWT denylist (real logout)

Access tokens now carry a unique `jti`. On login a session is recorded
(`jti → {user_id, ip, user_agent, created_at, expires_at}`). On logout — or an
explicit session revoke — the `jti` is added to the denylist for its remaining
lifetime, and `get_current_user` rejects any denylisted token with `401`.

API (all under `/v1/auth`):

| Method & path | Description |
| --- | --- |
| `POST /logout` | Revoke the presented access token + clear the refresh token. |
| `GET /sessions` | List the caller's active sessions (`current: true` marks this one). |
| `DELETE /sessions/{jti}` | Revoke one of the caller's sessions. |
| `POST /sessions/revoke-others` | Revoke every session except the current. |

Without Redis the denylist/sessions are process-local: logout still works on a
single node, but revocation is not shared across replicas.

## Distributed & scheduler locks

```python
from app.redis import locks

async with locks.lock("my-job", ttl_seconds=60) as token:
    if token is None:
        return            # another replica holds the lock — skip
    ...                   # critical section
```

Each in-process scheduler tick (workflow, monitoring, escalation, discovery,
universal discovery) is wrapped in `locks.scheduler_lock(<name>)` so that when
multiple API workers each run the loops, only one executes a given tick.
Acquisitions are exported as `nexora_lock_attempts_total{result="acquired|contended"}`.

Release uses an atomic compare-and-delete Lua script on real Redis (falls back
to a GET+DELETE when the server lacks scripting, e.g. `fakeredis`).

## Notification queue

When `NOTIFICATION_QUEUE_ENABLED=true`, `IncidentNotificationService` enqueues a
customer-safe payload instead of sending inline; a background drainer (started
in the app lifespan) delivers it via Slack/email out of band, retrying up to
`NOTIFICATION_QUEUE_MAX_ATTEMPTS`. Depth is exported as
`nexora_queue_depth{queue="notifications"}`. When disabled, notifications are
sent inline exactly as before.

## Health & metrics

* `/readyz` runs `check_redis`, which pings the shared client. It is
  **non-critical**: a Redis outage reports `degraded` but keeps the replica in
  rotation (features fall back in-process).
* Redis command latency is timed into `nexora_redis_command_duration_seconds{command}`.
* New metrics: `nexora_cache_events_total`, `nexora_lock_attempts_total`,
  `nexora_token_revocations_total`, plus the `notifications` queue-depth series.

## Tests

`app/tests/test_redis_layer.py` covers every feature against both the in-process
fallback and a real `redis.asyncio` client (via `fakeredis`, skipped when not
installed), plus the end-to-end logout/denylist and session list/revoke flows
through the auth API. The suite-wide `conftest.py` fixture resets the rate-limit
backend and all Redis fallbacks between tests so runs are order-independent.

## Operations

* The shared pool is opened lazily on first use and closed on app shutdown.
* A Redis outage degrades gracefully: rate limiting, cache, sessions, denylist,
  locks and the notification queue all fall back in-process; readiness reports
  `degraded` rather than failing.
* `docker-compose.yml` already provisions `redis:7-alpine` and wires
  `REDIS_URL` for the API service.
