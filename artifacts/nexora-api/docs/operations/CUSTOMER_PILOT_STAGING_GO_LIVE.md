# Customer Pilot Staging Go-Live Validation

Sprint 67F executes real operational validation in an internal/staging non-production environment and collects redacted go-live evidence.

## Script

```bash
docker compose run --rm \
  -e PYTHONPATH=/app \
  -e REDIS_URL=redis://redis:6379/0 \
  -e PILOT_67F_ARTIFACT_DIR=/app/artifacts/customer-pilot-staging-go-live-validation \
  -e DATABASE_URL=postgresql://nexora:nexora@db:5432/nexora \
  -v "$(pwd)/artifacts:/app/artifacts" \
  api python scripts/pilot_sprint67f_staging_validation.py
```

Backup/restore (requires `pg_dump` on db host):

```bash
DATABASE_URL=postgresql://nexora:nexora@localhost:5432/nexora \
  bash scripts/pilot_sprint67e_backup_validate.sh
```

Or run isolated restore via the db container (see Sprint 67F evidence `backup-restore-validation.json`).

## Evidence directory

`artifacts/customer-pilot-staging-go-live-validation/`

| File | Content |
|------|---------|
| `report.json` | Master redacted report |
| `configuration-validation.json` | Feature flags, migration, security config |
| `operations-readiness.json` | API operations readiness snapshot |
| `deployment-readiness.json` | API deployment readiness snapshot |
| `scheduler-reminder-validation.json` | Cron, lock, idempotency evidence |
| `smtp-validation.json` | NOT_CONFIGURED / DELIVERED / INSUFFICIENT_EVIDENCE |
| `alert-delivery-validation.json` | Alert test evidence |
| `backup-restore-validation.json` | pg_restore --list + isolated restore |
| `portal-dry-run.json` | Read-only portal journey |
| `runbook-walkthrough.json` | Operator drill documentation |
| `go-live-decision.md` | Final GO / NO_GO / INSUFFICIENT_EVIDENCE |
| `remediation-items.md` | Actionable blockers |

## Prerequisites

1. Internal pilot admin bootstrapped (`scripts/pilot_activation_bootstrap.py`)
2. `PILOT_MODE_ENABLED=true`, `PILOT_MODE_ALL_ORGS=false`, allowlist set
3. `DEBUG=false` for staging go-live (DEBUG=true → NO_GO)
4. API, worker, scheduler, PostgreSQL, Redis running
5. Alembic at `0039_customer_pilot_operations`

## GO criteria (scoped external onboarding)

Sprint 67F validates platform operations. Sprint 67G validates alerting and notifications.

**67F required evidence:** configuration, operations/deployment readiness, scheduler/reminders, backup/restore, portal dry-run, redaction scan.

**67G required evidence** (`artifacts/customer-pilot-alert-notification-validation/`):

| File | Required for GO |
|------|-----------------|
| `prometheus-scrape-validation.json` | Scrape healthy + all 6 pilot metrics queryable |
| `alert-rule-load-validation.json` | Rules loaded in Prometheus |
| `alert-receiver-receipt.json` | Firing + resolved webhook receipt |
| `alert-delivery-validation.json` | `status=DELIVERED` |
| `deployment-readiness-after.json` | `verdict=GO` |
| `smtp-validation.json` | Required only if `PILOT_EMAIL_NOTIFICATIONS_ENABLED=true` |

Run 67G after 67F:

```bash
docker compose -f docker-compose.yml -f docker-compose.customer-pilot-monitoring.yml up -d
docker compose -f docker-compose.yml -f docker-compose.customer-pilot-monitoring.yml run --rm \
  -e PYTHONPATH=/app \
  -e DATABASE_URL=postgresql://nexora:nexora@db:5432/nexora \
  -v "$(pwd)/artifacts:/app/artifacts" \
  api python scripts/pilot_sprint67g_alert_notification_validation.py
```

See [CUSTOMER_PILOT_ALERTING_VALIDATION.md](./CUSTOMER_PILOT_ALERTING_VALIDATION.md).

## Safety

- Internal/staging tenants only
- No provider mutation, execution, typed confirmation, or stage advancement
- Not a GA-ready declaration
- Artifacts fail closed on secret detection

## Related

- [CUSTOMER_PILOT_ALERTING_VALIDATION.md](./CUSTOMER_PILOT_ALERTING_VALIDATION.md)
- [CUSTOMER_PILOT_EMAIL_NOTIFICATION_POLICY.md](./CUSTOMER_PILOT_EMAIL_NOTIFICATION_POLICY.md)
- [CUSTOMER_PILOT_DEPLOYMENT_READINESS.md](./CUSTOMER_PILOT_DEPLOYMENT_READINESS.md)
- [CUSTOMER_PILOT_MONITORING.md](./CUSTOMER_PILOT_MONITORING.md)
- [CUSTOMER_PILOT_BACKUP_RESTORE.md](./CUSTOMER_PILOT_BACKUP_RESTORE.md)
