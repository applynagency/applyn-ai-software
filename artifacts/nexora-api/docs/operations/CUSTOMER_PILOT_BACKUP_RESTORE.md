# Customer Pilot Backup and Restore

Sprint 67E validates operational recovery for the customer pilot platform without touching external customer data.

## Scope

- Internal/non-production environments only
- Isolated restore database — **never** restore over the active production-like database
- Validates migration revision and pilot tables after restore

## Backup script

Primary backup: `scripts/backup/pg_backup.sh`

Required env:
- `DATABASE_URL`
- `BACKUP_GPG_PASSPHRASE` (encrypted backups mandatory in production)

Optional:
- `BACKUP_DIR` (default `/backups`)
- `BACKUP_RETENTION_DAYS` (default 14)
- `BACKUP_S3_BUCKET`

Kubernetes: `deploy/k8s/backup-cronjob.yaml` (02:00 UTC daily)

## Sprint 67E validation script

```bash
export DATABASE_URL="postgresql://..."
export SKIP_ENCRYPT=1          # dev/docker only
export SKIP_RESTORE=0          # set 1 for list-only validation
./scripts/pilot_sprint67e_backup_validate.sh
```

Produces: `artifacts/pilot-deployment-readiness/backup-validation.json`

### Validation steps

1. `pg_dump --format=custom` to timestamped archive
2. `pg_restore --list` integrity check
3. Count pilot table entries in archive listing
4. Create isolated database `nexora_restore_validate` (configurable via `RESTORE_DATABASE_NAME`)
5. `pg_restore` into isolated DB only
6. Verify `alembic_version` matches expected head (`0039_customer_pilot_operations`)
7. Confirm pilot tables present (`pilot_notification_deliveries`, `pilot_scheduler_health_snapshots`, etc.)

## RPO / RTO observations (internal test)

| Metric | Typical internal docker-compose observation |
|--------|---------------------------------------------|
| **RPO** | Last backup timestamp to failure point (daily cron = up to 24h; manual backup = minutes) |
| **RTO** | `pg_restore` duration + API restart + migration verify (test: minutes for dev DB size) |

Record actual timings from your `backup-validation.json` artifact after each drill.

## Restore safety rules

1. **Never** `pg_restore` into the active API database without maintenance window and explicit approval
2. Restore artifacts contain internal tenant data — treat as confidential
3. Redact database hostnames when sharing validation reports externally
4. Delete isolated restore database after validation: `DROP DATABASE nexora_restore_validate;`

## Deployment readiness integration

`GET /v1/pilot/deployment-readiness` reads `artifacts/pilot-deployment-readiness/backup-validation.json`:

- `valid: true` → backup integrity check passed
- Missing artifact → `INSUFFICIENT_EVIDENCE`

## Rollback reference

If Sprint 67D/67E migrations must be rolled back:

```bash
alembic downgrade 0038_customer_pilot_communications
```

Restore from pre-migration backup into isolated DB first to validate downgrade path.

## Related docs

- [CUSTOMER_PILOT_DEPLOYMENT_READINESS.md](./CUSTOMER_PILOT_DEPLOYMENT_READINESS.md)
- [CUSTOMER_PILOT_OPERATIONS_READINESS.md](./CUSTOMER_PILOT_OPERATIONS_READINESS.md)
