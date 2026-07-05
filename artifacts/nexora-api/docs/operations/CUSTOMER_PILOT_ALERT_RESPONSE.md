# Customer Pilot Alert Response

Operational response guide for customer pilot Prometheus alerts (Sprint 67E).

## Alert index

| Alert | Severity | First action |
|-------|----------|--------------|
| `CustomerPilotSchedulerUnhealthy` | critical | Check Redis + scheduler lock |
| `CustomerPilotWorkerUnhealthy` | critical | Restart Arq worker/scheduler |
| `CustomerPilotReminderCronStale` | warning | Review cron registration + worker logs |
| `CustomerPilotNotificationFailuresHigh` | warning | Inspect failed deliveries; requeue after fix |
| `CustomerPilotNotificationQueueStale` | warning | Process or requeue queued deliveries |
| `CustomerPilotSupportExportFailures` | info | Verify support bundle export path |
| `CustomerPilotApprovalRemindersNotRunning` | warning | Confirm reminder cron + PILOT_MODE_ENABLED |
| `CustomerPilotRedisUnavailable` | critical | Restore Redis; verify no duplicate reminders |
| `CustomerPilotDeploymentUnhealthy` | warning | Run deployment readiness checklist |

## CustomerPilotSchedulerUnhealthy

1. `GET /v1/pilot/operations-readiness` — note failed checks
2. Verify Redis: `redis-cli ping` from API/worker network
3. Check scheduler pod/container has `JOB_CRON_ENABLED=true`
4. Review `pilot_scheduler_health_snapshots` consecutive failures
5. See [CUSTOMER_PILOT_OPERATIONS_READINESS.md](./CUSTOMER_PILOT_OPERATIONS_READINESS.md)

**Customer communication:** Reminder delivery may be delayed; portal approval status remains authoritative.

## CustomerPilotWorkerUnhealthy

1. Confirm worker process running (`arq app.jobs.worker.WorkerSettings`)
2. Check last completed `cron_customer_pilot_approval_reminders` job
3. Restart worker; wait one cron cycle (default 300s)
4. Verify `nexora_customer_pilot_worker_healthy` returns to 1

**Do not:** Auto-approve, extend approvals, or execute operations.

## CustomerPilotNotificationFailuresHigh

1. `GET /v1/pilot/support/diagnostics` — `notification_health`
2. Fix root cause (SMTP, DB, in-app delivery)
3. Requeue failed deliveries: `POST /v1/pilot/communications/{id}/deliveries/{delivery_id}/requeue`
4. See [CUSTOMER_PILOT_NOTIFICATION_RECOVERY.md](./CUSTOMER_PILOT_NOTIFICATION_RECOVERY.md)

## CustomerPilotRedisUnavailable

1. Fail closed — do not claim reminders are operating
2. Scheduler lock prevents duplicate sends on recovery
3. Customer portal shows degraded operational status
4. After Redis recovery, verify operations readiness returns to GO

## CustomerPilotDeploymentUnhealthy

1. `GET /v1/pilot/deployment-readiness`
2. Resolve migration, feature flag, CORS, rate limit, or backup gaps
3. Run `scripts/pilot_sprint67e_deployment_readiness.py`
4. See [CUSTOMER_PILOT_DEPLOYMENT_READINESS.md](./CUSTOMER_PILOT_DEPLOYMENT_READINESS.md)

## Escalation

- **P1:** Scheduler + Redis both unhealthy during active customer pilot
- **P2:** Notification failures with pending approvals nearing expiry
- **P3:** Deployment readiness INSUFFICIENT_EVIDENCE (SMTP/alert not verified)

## Resolution proof

Record in internal ticket:
- Alert name and fired_at
- Remediation steps taken
- `operations-readiness` / `deployment-readiness` verdict after recovery
- No provider mutation performed during incident response
