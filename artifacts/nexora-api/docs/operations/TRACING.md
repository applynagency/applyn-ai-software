# Distributed Tracing (OpenTelemetry)

Nexora supports end-to-end distributed tracing via OpenTelemetry. It is
**opt-in** (`TRACING_ENABLED=false` by default) and every OpenTelemetry import is
lazy, so the application boots and runs fine with no OpenTelemetry packages
installed.

## What is traced

| Layer | Instrumentation | Spans |
| ----- | --------------- | ----- |
| **FastAPI** (incoming HTTP) | `opentelemetry-instrumentation-fastapi` (ASGI middleware) | `GET /v1/...` server spans |
| **Database** | `opentelemetry-instrumentation-sqlalchemy` (engine) | one span per SQL statement |
| **HTTP client** (outbound) | `opentelemetry-instrumentation-httpx` | one span per outbound request (integration verification, monitoring ingestion, discovery — all go through the SSRF-safe httpx client) |
| **Redis** | `opentelemetry-instrumentation-redis` | one span per Redis command (rate limiter) |
| **LLM** | custom span `llm.request` (`app/services/ai_team_runner.py`) | provider/model/outcome, `client` kind |
| **Background tasks** | custom spans `scheduler.*` (`app/services/*_scheduler.py`) | one span per scheduler tick (`consumer` kind) for workflow / monitoring / escalation / discovery / universal-discovery |

Custom spans are created through `app.observability.tracing.start_as_current_span`,
which is a safe no-op when tracing is unavailable or uninitialized.

## Exporters

Configurable via `TRACING_EXPORTER`:

| Value     | Backend | Package | Default endpoint |
| --------- | ------- | ------- | ---------------- |
| `otlp`    | OTLP/HTTP (Collector, Jaeger ≥1.35, Grafana Tempo, …) | `opentelemetry-exporter-otlp-proto-http` *(shipped)* | `http://localhost:4318/v1/traces` |
| `zipkin`  | Zipkin  | `opentelemetry-exporter-zipkin-json` *(shipped)* | `http://localhost:9411/api/v2/spans` |
| `jaeger`  | Jaeger (thrift) | `opentelemetry-exporter-jaeger` *(optional extra)* | agent `localhost:6831` |
| `console` | stdout (debugging) | bundled in the SDK | — |
| `none`    | provider set up, no export | — | — |

`TRACING_ENDPOINT` overrides the exporter's default endpoint. If the configured
exporter package is missing, tracing logs a warning and falls back to the
console exporter rather than failing startup.

> **Jaeger note.** The dedicated Jaeger exporter is deprecated upstream and is
> therefore an **optional** extra rather than a default dependency. Install it
> with `pip install opentelemetry-exporter-jaeger`, or (recommended) point the
> `otlp` exporter at Jaeger, which ingests OTLP natively since v1.35.

## Configuration

| Setting | Default | Purpose |
| ------- | ------- | ------- |
| `TRACING_ENABLED` | `false` | Master switch. |
| `OTEL_SERVICE_NAME` | `nexora-api` | `service.name` resource attribute. |
| `TRACING_EXPORTER` | `otlp` | `otlp` \| `jaeger` \| `zipkin` \| `console` \| `none`. |
| `TRACING_ENDPOINT` | `None` | Override the exporter endpoint. |
| `TRACING_SAMPLE_RATIO` | `1.0` | Parent-based ratio sampler (`0.0`–`1.0`). |

Spans are exported via a `BatchSpanProcessor` and tagged with a resource of
`service.name`, `service.version` and `deployment.environment`.

### Example

```bash
TRACING_ENABLED=true \
TRACING_EXPORTER=otlp \
TRACING_ENDPOINT=http://otel-collector:4318/v1/traces \
TRACING_SAMPLE_RATIO=0.1
```

## How it is wired

- `init_tracing(app)` is called once at import time in `app/main.py` (no-op when
  disabled). It builds the `TracerProvider`, sets it globally, and instruments
  FastAPI, SQLAlchemy, httpx and Redis — each guarded independently so a missing
  package degrades gracefully.
- `shutdown_tracing()` flushes/zeros the provider on application shutdown.

## Files

| File | Change |
| ---- | ------ |
| `app/observability/tracing.py` | New — provider/exporter construction, library instrumentation, `start_as_current_span`. |
| `app/main.py` | Calls `init_tracing(app)` (import time) and `shutdown_tracing()` (shutdown). |
| `app/services/ai_team_runner.py` | `llm.request` span around the LLM call. |
| `app/services/{workflow,monitoring,discovery}_scheduler.py` | `scheduler.*` span per background tick. |
| `app/core/config.py` | Tracing settings. |
| `app/tests/test_tracing.py` | Tests (skipped when OpenTelemetry is absent). |
| `requirements.txt` | OpenTelemetry SDK + OTLP/Zipkin exporters + instrumentation packages. |

## Testing

```bash
pytest app/tests/test_tracing.py
```

Skips automatically when the OpenTelemetry SDK is not installed. The suite
verifies span creation/attributes, nested-span parenting, exception recording,
exporter selection (including fallback), the service resource, and the
disabled-mode no-op.

## Security note

Traces can contain route templates, SQL statements and span attributes. Export
only to trusted collectors inside your network, and keep `TRACING_SAMPLE_RATIO`
modest in production to bound overhead.
