# Customer Pilot Alerting Validation (Sprint 67G)

Internal/staging operational validation for Prometheus scrape, alert rules, and alert delivery.

## Prerequisites

- Sprint 67F staging validation complete (operations readiness GO)
- Docker Compose stack running (`api`, `worker`, `scheduler`, `db`, `redis`)
- Internal org allowlisted (`PILOT_MODE_ENABLED=true`, `PILOT_MODE_ALL_ORGS=false`)

## Monitoring stack

```bash
cd artifacts/nexora-api
docker compose -f docker-compose.yml -f docker-compose.customer-pilot-monitoring.yml up -d
```

This starts:

| Service | Purpose |
|---------|---------|
| `customer-pilot-prometheus` | Scrapes `api:8000/nexora-api/metrics`, loads alert rules |
| `customer-pilot-alertmanager` | Routes alerts to internal webhook |
| `customer-pilot-alert-receiver` | Records firing/resolved events (redacted) |

The API overlay enables `PILOT_ALERT_TEST_ENABLED=true` and sets `PILOT_ALERT_WEBHOOK_URL` for readiness evaluation only (URL never exported in artifacts).

## Validation script

```bash
docker compose -f docker-compose.yml -f docker-compose.customer-pilot-monitoring.yml run --rm \
  -e PYTHONPATH=/app \
  -e DATABASE_URL=postgresql://nexora:nexora@db:5432/nexora \
  -v "$(pwd)/artifacts:/app/artifacts" \
  api python scripts/pilot_sprint67g_alert_notification_validation.py
```

## Alert drill flow

1. Script captures `deployment-readiness-before.json`
2. Sets controlled test signal via `POST /v1/pilot/internal/alert-test-signal?value=1`
3. Prometheus evaluates `CustomerPilotAlertDeliveryTest` rule
4. Alertmanager delivers to internal webhook receiver
5. Receiver records firing event in `alert-receiver-receipt.json`
6. Script clears signal (`value=0`) and waits for resolved event
7. Script captures `deployment-readiness-after.json`

No Redis/worker outage, provider mutation, or pilot execution occurs.

## Evidence directory

`artifacts/customer-pilot-alert-notification-validation/`

## GO criteria

- Prometheus scrape healthy with all required `nexora_customer_pilot_*` metrics queryable
- Alert rules loaded without errors
- Alert firing and resolution received by internal webhook
- `GET /v1/pilot/deployment-readiness` = GO after evidence bridge
- SMTP validated only if `PILOT_EMAIL_NOTIFICATIONS_ENABLED=true`

## Related

- [CUSTOMER_PILOT_EMAIL_NOTIFICATION_POLICY.md](./CUSTOMER_PILOT_EMAIL_NOTIFICATION_POLICY.md)
- [CUSTOMER_PILOT_STAGING_GO_LIVE.md](./CUSTOMER_PILOT_STAGING_GO_LIVE.md)
- [CUSTOMER_PILOT_MONITORING.md](./CUSTOMER_PILOT_MONITORING.md)
