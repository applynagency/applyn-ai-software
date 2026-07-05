# Customer Pilot Monitoring

Sprint 67E wires customer pilot operational metrics into Prometheus and documents PromQL queries for operator dashboards.

## Metrics (Sprint 67D/67E)

| Metric | Type | Description |
|--------|------|-------------|
| `nexora_customer_pilot_scheduler_healthy` | Gauge | 1 when operations readiness is GO |
| `nexora_customer_pilot_worker_healthy` | Gauge | 1 when worker heartbeat recent |
| `nexora_customer_pilot_deployment_healthy` | Gauge | 1 when deployment readiness is GO |
| `nexora_customer_pilot_approval_reminders_total` | Counter | Reminders sent by type |
| `nexora_customer_pilot_approval_reminder_failures_total` | Counter | Reminder cron failures |
| `nexora_customer_pilot_notification_deliveries_total` | Counter | Deliveries by status |
| `nexora_customer_pilot_notification_failures_total` | Counter | Failed deliveries |
| `nexora_customer_pilot_notification_retry_total` | Counter | Retry attempts |
| `nexora_customer_pilot_notification_queue_oldest_seconds` | Gauge | Oldest queued delivery age |
| `nexora_customer_pilot_support_bundle_total` | Counter | Support bundles generated |

## Scrape configuration

API exposes metrics at `{BASE_PATH}/metrics` (default `/nexora-api/metrics`).

Docker Compose: scrape the `api` service on port 8000.

Internal pilot stack: see `deploy/pilot-internal/prometheus.yml`.

## Alert rules

Version-controlled rules: `deploy/monitoring/customer-pilot-alerts.yml`

Load into Prometheus:

```yaml
rule_files:
  - /etc/prometheus/rules/customer-pilot-alerts.yml
```

## PromQL — operational health dashboard

### Scheduler healthy
```promql
nexora_customer_pilot_scheduler_healthy
```

### Worker healthy
```promql
nexora_customer_pilot_worker_healthy
```

### Deployment readiness
```promql
nexora_customer_pilot_deployment_healthy
```

### Notification failure rate (1h)
```promql
increase(nexora_customer_pilot_notification_failures_total[1h])
```

### Oldest queued notification
```promql
nexora_customer_pilot_notification_queue_oldest_seconds
```

### Reminder send rate (24h)
```promql
sum(increase(nexora_customer_pilot_approval_reminders_total[24h])) by (reminder_type)
```

### Support bundles generated (24h)
```promql
increase(nexora_customer_pilot_support_bundle_total[24h])
```

## API readiness endpoints

| Endpoint | Scope |
|----------|-------|
| `GET /v1/pilot/operations-readiness` | Background job health |
| `GET /v1/pilot/deployment-readiness` | Full deployment validation |
| `GET /livez`, `GET /readyz` | Platform probes |

Customer routes receive only sanitized `operational_status` — never deployment topology.

## Test alert procedure

1. Configure internal receiver: `PILOT_ALERT_WEBHOOK_URL` or `PILOT_ALERT_EMAIL`
2. Temporarily set `nexora_customer_pilot_scheduler_healthy` to 0 in staging or wait for real degradation
3. Confirm `CustomerPilotSchedulerUnhealthy` fires in Prometheus
4. Record proof in `artifacts/pilot-deployment-readiness/alert-test.json`
5. Set `PILOT_ALERT_TEST_DELIVERED=1` when receipt confirmed

If no receiver is configured, mark alert delivery **INSUFFICIENT_EVIDENCE** — do not claim alerting works.

## Grafana

Import `deploy/observability/grafana-nexora-overview.json` and add a Customer Pilot row with the PromQL queries above.

## Safety

Monitoring wiring is read-only. Alert rules do not trigger provider mutation or pilot execution.
