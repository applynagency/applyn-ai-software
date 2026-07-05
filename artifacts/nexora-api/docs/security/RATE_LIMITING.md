# Distributed Rate Limiting

Nexora throttles abuse-prone endpoints with a **distributed sliding-window**
rate limiter. Limits are enforced in middleware before a request reaches the
route, are shared across every API replica via Redis, and are applied per
**IP**, per **user**, and per **organization**.

This addresses audit finding **F-SEC4** (no rate limiting on authentication or
write endpoints) and activates the previously-unused Redis dependency.

## What is limited

Endpoints are matched by **path suffix** (and, for webhooks, by substring), so
the `BASE_PATH` and `/v1` prefixes do not matter.

| Rule                    | Endpoint                                   | Scopes                | Default limit |
| ----------------------- | ------------------------------------------ | --------------------- | ------------- |
| `auth_login`            | `POST .../auth/login`                      | IP                    | `5 / 60s`     |
| `auth_register`         | `POST .../auth/register`                   | IP                    | `5 / 300s`    |
| `auth_refresh`          | `POST .../auth/refresh`                    | IP, user              | `30 / 60s`    |
| `integrations_connect`  | `POST .../integrations/connect`            | IP, user, organization| `20 / 60s`    |
| `webhooks`              | `POST .../monitoring/ingest`, `.../webhooks/*` | IP                | `240 / 60s`   |

Each in-scope identity is checked **independently** and the **most restrictive
scope wins**. For example, `integrations/connect` is rejected if *any* of the
caller's IP, user, or organization windows is full — so one noisy user cannot
exhaust an organization's budget, and one organization cannot be DoS'd by a
single IP.

Unauthenticated endpoints (`login`, `register`) are limited per IP only because
no identity exists yet. Authenticated endpoints additionally derive the `user`
(`sub`) and `organization` (`organization_id`) identities directly from the
bearer token, falling back to an `X-Organization-Id` header when present.

## Algorithm

A **sliding window log** backed by a Redis sorted set (one entry per request,
score = timestamp):

1. Drop entries older than `now - window`.
2. Count the remaining entries.
3. If the count is below the limit, record the request and **allow**; otherwise
   **reject**.

The check-and-record runs atomically inside a single Lua script, so the window
is correct even with many concurrent replicas. Because a rejected request is
**not** recorded, a client is never permanently locked out once the window
slides forward. This is a true sliding window — there is no fixed-bucket burst
at window boundaries.

## Response when limited

Rejected requests return **HTTP 429** with a JSON body and standard headers:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 42
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 42
X-RateLimit-Scope: ip
Content-Type: application/json

{
  "detail": "Rate limit exceeded. Please retry later.",
  "scope": "ip",
  "limit": 5,
  "window_seconds": 60,
  "retry_after": 42
}
```

Allowed responses carry `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and
`X-RateLimit-Reset` for the most-constrained scope so clients can self-throttle.

## Backends

- **Redis (production / distributed):** set `REDIS_URL`. Limits are shared
  across all API instances. The `redis` client is imported lazily.
- **In-memory (fallback):** when `REDIS_URL` is unset, or the `redis` package /
  server is unavailable, the limiter transparently falls back to a process-local
  window (logged as `rate_limit_backend_inmemory[_fallback]`). This keeps
  single-node deployments, local development, and tests working. Note: an
  in-memory window is **not** shared across replicas — configure Redis for any
  multi-instance deployment.

## Configuration

All settings live in `app/core/config.py` (env-overridable). Limits use the
`"<max_requests>/<window_seconds>"` format and are validated at startup.

| Setting                            | Default       | Purpose                                              |
| ---------------------------------- | ------------- | ---------------------------------------------------- |
| `RATE_LIMIT_ENABLED`               | `true`        | Master switch for the middleware.                    |
| `REDIS_URL`                        | `None`        | Redis connection URL; enables the distributed backend.|
| `RATE_LIMIT_TRUST_FORWARDED_FOR`   | `true`        | Use `X-Forwarded-For` / `X-Real-IP` for the client IP.|
| `RATE_LIMIT_FAIL_OPEN`             | `true`        | On backend outage: allow (`true`) or block (`false`).|
| `RATE_LIMIT_KEY_PREFIX`            | `nexora:rl`   | Redis key namespace.                                 |
| `RATE_LIMIT_AUTH_LOGIN`            | `5/60`        | Login limit.                                         |
| `RATE_LIMIT_AUTH_REGISTER`         | `5/300`       | Registration limit.                                  |
| `RATE_LIMIT_AUTH_REFRESH`          | `30/60`       | Token refresh limit.                                 |
| `RATE_LIMIT_INTEGRATIONS_CONNECT`  | `20/60`       | Integration connect limit.                           |
| `RATE_LIMIT_WEBHOOKS`              | `240/60`      | Webhook ingestion limit.                             |

### Operational notes

- **`X-Forwarded-For` trust.** The IP is taken from the left-most
  `X-Forwarded-For` entry when `RATE_LIMIT_TRUST_FORWARDED_FOR` is true. This is
  correct **only when the API sits behind a trusted proxy/load balancer that
  overwrites the header.** If the app is internet-facing without such a proxy,
  set this to `false` so the real socket peer is used and clients cannot spoof
  the header to bypass per-IP limits.
- **Fail-open vs fail-closed.** The default favours availability: if Redis is
  unreachable, traffic is allowed (and logged). Set `RATE_LIMIT_FAIL_OPEN=false`
  to fail closed (reject with 429) if you prefer strict enforcement during an
  outage.

## Files

| File                                   | Change                                               |
| -------------------------------------- | ---------------------------------------------------- |
| `app/security/rate_limit.py`           | New — sliding-window algorithm, Redis + in-memory backends, backend factory. |
| `app/middleware/rate_limit.py`         | New — `RateLimitMiddleware`: matching, scope resolution, 429 response. |
| `app/core/config.py`                   | New rate-limit + `REDIS_URL` settings.               |
| `app/main.py`                          | Registers `RateLimitMiddleware`; closes the backend on shutdown. |
| `requirements.txt`                     | Adds `redis` (prod) and `fakeredis[lua]` (tests).    |
| `app/tests/test_rate_limit.py`         | Unit tests — parsing, sliding window, Redis (Lua) backend. |
| `app/tests/test_rate_limit_middleware.py` | Integration tests — per IP/user/org, 429 + headers, isolation, fail-open/closed. |

## Migration notes

- **Backward compatible.** With `REDIS_URL` unset the limiter uses the in-memory
  fallback; no infrastructure change is required to deploy. To enable
  distributed limiting, provision Redis and set `REDIS_URL`
  (e.g. `redis://redis:6379/0`).
- **No API contract change** for well-behaved clients; only abusive callers see
  `429`. Clients should honour `Retry-After`.

## Testing

```bash
# Unit + integration (in-memory backend; no Redis required)
pytest app/tests/test_rate_limit.py app/tests/test_rate_limit_middleware.py

# The Redis (Lua) backend test runs automatically when fakeredis[lua] is
# installed; it is skipped otherwise.
```

The Redis Lua script has been validated against both `fakeredis[lua]` and a real
`redis:7` server, producing identical sliding-window results to the in-memory
backend.
