# Enterprise Observability Platform (Sprint 65B)

Nexora's unified observability layer extends existing monitoring, service health,
architecture discovery, and search — it does **not** duplicate those engines.

## Architecture

`ObservabilityPlatformService` orchestrates:

| Capability | Reused engine |
|------------|---------------|
| Metrics | Provider registry + `MonitoringEngine` |
| Logs | Loki/Elastic/Cloud provider adapters |
| Traces | Tempo/Jaeger/Zipkin adapters |
| Service map | `ArchitectureDiscoveryService` (Knowledge Graph) |
| SLOs / error budgets | `ServiceHealthService` |
| Alert intelligence | `MonitoringAlertRepository` + grouping heuristics |
| Correlation | Cross-signal timeline builder |
| Dashboards | Monitoring + SLO + golden signals |

All data is **organization scoped** via `OrgContext`.

## API (`/v1/observability`)

| Endpoint | Description |
|----------|-------------|
| `GET /providers` | Supported backend kinds |
| `GET/POST /integrations` | Org-scoped provider config |
| `POST /metrics/query` | PromQL-style metric query |
| `GET /metrics/discover` | Metric discovery |
| `GET /metrics/top` | Top metrics |
| `POST /logs/search` | Log search (regex, filters) |
| `GET/POST /logs/saved-searches` | Saved searches |
| `POST /traces/search` | Trace search |
| `GET /service-map` | Live topology with overlays |
| `GET /slo` | SLO dashboard |
| `POST /slo/evaluate` | Run SLO evaluations |
| `GET /error-budget` | Error budget posture |
| `GET /alerts/intelligence` | AI alert grouping & storms |
| `POST/GET /correlation` | Investigation timelines |
| `GET /dashboard` | Golden signals + infra/app views |

## Integrations

**Metrics:** Prometheus, OpenTelemetry, CloudWatch, Azure Monitor, GCP Monitoring, Datadog (read-only), New Relic (read-only), Custom

**Logs:** Loki, Elastic, CloudWatch, Azure Monitor, GCP Monitoring

**Traces:** Tempo, Jaeger, Zipkin, OpenTelemetry

## Domain events

- `MetricThresholdExceeded`
- `LogPatternDetected`
- `TraceAnomalyDetected`
- `SLOBreach`
- `ErrorBudgetBurning`
- `GoldenSignalChanged`
- `AlertCorrelated`
- `RootCauseDetected`

## AI tools (grounded)

- `observability.explain_metric`
- `observability.find_root_cause`
- `observability.trace_request`
- `observability.explain_logs`
- `observability.detect_anomaly`
- `observability.optimize_alerts`
- `observability.suggest_slo`

Every tool response includes an `evidence` block with live query results.

## Prometheus metrics

- `nexora_obs_query_duration_seconds`
- `nexora_obs_ingestion_total`
- `nexora_obs_slo_evaluations_total`
- `nexora_obs_correlation_duration_seconds`
- `nexora_obs_ai_investigations_total`
- `nexora_obs_dashboard_duration_seconds`

## Configuration

- `OBSERVABILITY_PLATFORM_ENABLED=true` (default)

## Database

Migration `0028_observability_platform` creates:

- `obs_integrations`
- `obs_saved_searches`
- `obs_correlation_timelines`
- `obs_slo_evaluations`
- `obs_alert_groups`

## UI

Pages under `/observability-platform/*` in the Observability nav module.
