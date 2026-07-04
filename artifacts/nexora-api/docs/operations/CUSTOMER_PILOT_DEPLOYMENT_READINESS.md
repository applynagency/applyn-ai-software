# Customer Pilot Deployment Readiness

Sprint 67E validates production-like deployment configuration before onboarding the first external customer.

## Endpoint

`GET /v1/pilot/deployment-readiness` — operator-only; never exposed on customer routes.

Returns `GO` / `NO_GO` / `INSUFFICIENT_EVIDENCE` with remediation steps.

## Verdicts

| Verdict | Meaning |
|---------|---------|
| `GO` | All critical deployment and operations checks passed; non-critical gaps acceptable |
| `NO_GO` | Critical failure (migration, Redis, allowlist, debug, health) |
| `INSUFFICIENT_EVIDENCE` | SMTP, alerting, backup, or dry-run not yet validated |

## Checklist

### Platform
- [ ] API running current image (`APP_VERSION`)
- [ ] Database at migration `0039_customer_pilot_operations`
- [ ] Exactly one Alembic head
- [ ] `/livez` and `/readyz` passing

### Pilot configuration
- [ ] `PILOT_MODE_ENABLED=true`
- [ ] `PILOT_MODE_ALL_ORGS=false`
- [ ] `PILOT_ORGANIZATION_IDS` contains internal tenant only
- [ ] Customer portal enabled for allowlisted org

### Security
- [ ] `DEBUG=false`
- [ ] JWT secret not a known placeholder
- [ ] No wildcard CORS (`*`)
- [ ] `RATE_LIMIT_ENABLED=true`

### Operations (67D)
- [ ] Redis reachable from API and worker
- [ ] Arq worker processing jobs
- [ ] Approval reminder cron registered on scheduler
- [ ] Scheduler lock functional
- [ ] Operations readiness not NO_GO

### Observability
- [ ] `METRICS_ENABLED=true`
- [ ] Prometheus scraping `/nexora-api/metrics`
- [ ] `deploy/monitoring/customer-pilot-alerts.yml` loaded
- [ ] Test alert delivered (or mark INSUFFICIENT_EVIDENCE)

### Recovery
- [ ] Backup created and validated (`scripts/pilot_sprint67e_backup_validate.sh`)
- [ ] Isolated restore tested

### Internal dry run
- [ ] `scripts/pilot_sprint67e_deployment_readiness.py` completed
- [ ] Portal flow validated without provider execution
- [ ] Reminder idempotency verified
- [ ] Failure drills passed

## Validation script

```bash
# Inside docker network
docker compose run --rm api python scripts/pilot_sprint67e_deployment_readiness.py

# Backup validation
docker compose exec db bash -c 'DATABASE_URL=... ./scripts/pilot_sprint67e_backup_validate.sh'
```

Artifacts: `artifacts/pilot-deployment-readiness/`

## UI

Pilot Center → **Deployment readiness** (`/pilot/deployment-readiness`)

Links to Operations Health and dry-run status card.

## Dry run scope

The internal dry run:
- Uses internal org `41a17fb0-...` (configurable via `PILOT_INTERNAL_ORG_ID`)
- Does **not** execute provider operations
- Does **not** perform typed confirmation
- Does **not** advance pilot stages beyond existing state
- May skip reminder test if no PENDING approval exists

If the internal live pilot is CLOSED, the dry run still validates portal read paths and creates a separate dry-run org only when needed for new approval scenarios.

## Failure drills (internal)

| Drill | Expected outcome |
|-------|------------------|
| Redis unavailable | Operations/deployment NO_GO; no duplicate reminders |
| Worker unavailable | Cron stale; approval state unchanged |
| Notification failure | FAILED/RETRYING; requeue works; approval unchanged |
| Export redaction failure | Fail closed; no unsafe artifact |

## Metrics

- `nexora_customer_pilot_deployment_healthy`

## Events

- `CustomerPilotDeploymentReadinessEvaluated`
- `CustomerPilotDryRunCompleted`

## Not GA-ready

Deployment readiness GO does **not** mean GA-ready or approved for unrestricted external customers. It means internal production-like validation passed.

## Related docs

- [CUSTOMER_PILOT_MONITORING.md](./CUSTOMER_PILOT_MONITORING.md)
- [CUSTOMER_PILOT_ALERT_RESPONSE.md](./CUSTOMER_PILOT_ALERT_RESPONSE.md)
- [CUSTOMER_PILOT_BACKUP_RESTORE.md](./CUSTOMER_PILOT_BACKUP_RESTORE.md)
- [CUSTOMER_PILOT_OPERATIONS_READINESS.md](./CUSTOMER_PILOT_OPERATIONS_READINESS.md)
