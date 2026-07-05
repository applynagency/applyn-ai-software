# Customer Pilot Operations Readiness

Sprint 67D adds a production readiness evaluator for pilot background jobs before onboarding the first external customer.

## Migration

- **Head:** `0039_customer_pilot_operations` (chains from `0038_customer_pilot_communications`)
- **Tables:**
  - `pilot_notification_deliveries` — durable delivery tracking with idempotency
  - `pilot_scheduler_health_snapshots` — cron run history and consecutive failure counts

## Endpoint

`GET /v1/pilot/operations-readiness` — internal operator view with full checks and remediation steps.

Customer-safe subset is merged into `GET /v1/customer-pilot/readiness` as `operational_status` (no infrastructure names).

## Verdicts

| Verdict | Meaning |
|---------|---------|
| `GO` | All critical checks passed |
| `NO_GO` | One or more critical checks failed |
| `INSUFFICIENT_EVIDENCE` | Non-critical gaps only (e.g. reminder cron never ran) |

## Checks

- Redis connectivity
- Arq worker heartbeat (last completed reminder job within 2h when job queue enabled)
- Approval reminder cron registration (`PILOT_MODE_ENABLED` + `JOB_CRON_ENABLED`)
- Scheduler lock acquisition capability
- Reminder job last successful run (staleness threshold)
- Reminder consecutive failure count (< 3)
- Notification queue age and failed-delivery backlog (non-critical)
- Clock / UTC sanity
- Email provider configured/unconfigured only (never exposes SMTP secrets)

Each failed check includes a safe remediation instruction in `remediation_steps`.

## Metrics

- `nexora_customer_pilot_scheduler_healthy`
- `nexora_customer_pilot_worker_healthy`

## Events

- `CustomerPilotOperationsReadinessEvaluated`
- `CustomerPilotSchedulerDegraded` (when verdict is not `GO`)

## Degradation — Redis unavailable

- Scheduler readiness → `NO_GO` or `INSUFFICIENT_EVIDENCE`
- Do not claim reminders are operating
- `scheduler_lock` prevents duplicate reminder sends when Redis recovers

## Degradation — Arq worker unavailable

- Existing approvals remain valid until expiry
- No automatic state changes except normal API-time expiry validation
- Customer portal shows safe notice that reminder delivery may be delayed

## UI

- Internal: `/pilot/operations-health` under Pilot Center
- Customer: operational badges on `/customer-pilot/readiness`

## Rollback

If this migration must be rolled back:

```bash
alembic downgrade 0038_customer_pilot_communications
```

This drops `pilot_notification_deliveries` and `pilot_scheduler_health_snapshots`. Sprint 67C communications tables remain intact.

## Safety confirmation

This sprint adds **no** provider mutation, execution, confirmation, rollback, or stage advancement paths.
