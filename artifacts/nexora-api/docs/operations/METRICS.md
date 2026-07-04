# Prometheus Metrics

Nexora exposes application, dependency and business metrics in the Prometheus
text exposition format at:

```
GET /nexora-api/metrics
```

(Customer-facing Metrics Explorer UI is served at ``GET /metrics`` as part of the SPA.)

Built on [`prometheus_client`](https://github.com/prometheus/client_python). The
dependency is **optional at runtime**: if it is not installed the application
still boots and ``/nexora-api/metrics`` returns `503` (`metrics unavailable`).

## Metric inventory

| Metric | Type | Labels | Meaning |
| ------ | ---- | ------ | ------- |
| `nexora_http_requests_total` | Counter | `method`, `path`, `status` | Request count **and** status codes. `path` is the route *template* (e.g. `/v1/incidents/{id}`). |
| `nexora_http_request_duration_seconds` | Histogram | `method`, `path` | Request duration. |
| `nexora_database_query_duration_seconds` | Histogram | `operation` (`SELECT`/`INSERT`/`UPDATE`/`DELETE`/`OTHER`/…) | Database latency, timed via SQLAlchemy cursor events. |
| `nexora_redis_command_duration_seconds` | Histogram | `command` (`eval`/`ping`) | Redis latency (rate-limiter commands). |
| `nexora_queue_depth` | Gauge | `queue` | Pending items per internal queue. |
| `nexora_scheduler_jobs` | Gauge | `scheduler` | Background scheduler state (`1` running, `0` stopped/disabled). |
| `nexora_llm_requests_total` | Counter | `provider`, `model`, `status` (`success`/`error`/`simulated`) | LLM requests. |
| `nexora_organizations_total` | Gauge | — | Number of organizations. |
| `nexora_incidents_total` | Gauge | `status` | Incident count by lifecycle status (`OPEN` … `CLOSED`). |

`*_total` counters and `*_duration_seconds` histograms are updated as events
occur; the gauges (`scheduler_jobs`, `organizations_total`, `incidents_total`,
`queue_depth`) reflect the **moment of the scrape** — they are refreshed inside
the `/metrics` handler.

## How each metric is collected

- **HTTP** — `app.middleware.metrics.MetricsMiddleware` wraps every request,
  recording count/status and duration against the matched route template
  (unmatched requests use `<unmatched>`). The `/metrics` scrape is excluded.
- **Database latency** — `before/after_cursor_execute` events on the SQLAlchemy
  engine time every query (`app.observability.metrics.instrument_database`).
- **Redis latency** — the Redis rate-limit backend records `eval`/`ping`
  durations.
- **LLM requests** — `AITeamAgentRunner` records `success` / `error` for live
  Anthropic calls and `simulated` when no key is configured.
- **Schedulers** — refreshed from the background-task registry shared with the
  health probes; each enabled loop reports `1` while its task is alive.
- **Organizations / Incidents** — counted from the database at scrape time.
- **Queue depth** — a settable gauge; producers call
  `app.observability.metrics.set_queue_depth(name, value)`. The
  `monitoring_dead_letter` series is seeded at `0`.

All recording helpers are **best-effort** and wrapped in `try/except`: a metrics
failure can never break a request, query, or LLM call.

## Configuration / scraping

No configuration is required. Point Prometheus at the endpoint:

```yaml
scrape_configs:
  - job_name: nexora-api
    metrics_path: /metrics
    static_configs:
      - targets: ["nexora-api:8000"]
```

`/metrics` is unauthenticated and intended to be reached only from inside the
cluster / behind the ingress (the same model as the health probes). Restrict it
at the network/ingress layer if your threat model requires it.

## Files

| File | Change |
| ---- | ------ |
| `app/observability/metrics.py` | New — registry, metric definitions, recording helpers, DB instrumentation, scrape-time gauge refresh. |
| `app/middleware/metrics.py` | New — `MetricsMiddleware` (request count/duration/status). |
| `app/main.py` | Initializes metrics + DB instrumentation in lifespan, registers the middleware, serves `/metrics`. |
| `app/security/rate_limit.py` | Records Redis command latency. |
| `app/services/ai_team_runner.py` | Records LLM request outcomes. |
| `app/tests/test_metrics.py` | Unit + middleware/endpoint tests (skipped if `prometheus_client` absent). |
| `requirements.txt` | Adds `prometheus-client`. |

## Testing

```bash
pytest app/tests/test_metrics.py
```

The suite skips automatically when `prometheus_client` is not installed.
