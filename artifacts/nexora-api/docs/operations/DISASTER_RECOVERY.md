# Disaster Recovery Runbook (Sprint 61B)

This runbook covers backup, restore and recovery for Nexora's stateful
dependencies (PostgreSQL is the only source of truth; Redis is a cache/coordination
layer and is rebuildable).

## Objectives

| Metric | Target |
|---|---|
| RPO (max data loss) | ≤ 24h (nightly backup) — tighten with WAL archiving for ≤ 5 min |
| RTO (max downtime)  | ≤ 1h (restore + redeploy) |

## What is backed up

- **PostgreSQL** — full logical backup (`pg_dump` custom format, compressed,
  **GPG/AES-256 encrypted**) via `scripts/backup/pg_backup.sh`, scheduled by
  `deploy/k8s/backup-cronjob.yaml` (nightly, 14-day retention, optional S3).
- **Redis** — *not* backed up by design. Sessions/denylist/cache/locks/queue all
  rebuild from PostgreSQL + live traffic. The durable `jobs` table is the source
  of truth for in-flight work, so queue contents survive a Redis loss.

## Backups are verified, not assumed

`scripts/backup/pg_restore_verify.sh <backup.dump.gpg>` decrypts the latest
backup, restores it into a scratch database and asserts table count + Alembic
head. Run it in CI/scheduled so a broken backup is caught before it is needed.

## Restore procedure (PostgreSQL data loss / corruption)

1. **Stop writers** — scale API/worker/scheduler to 0:
   ```bash
   kubectl -n nexora scale deploy/nexora-api deploy/nexora-worker deploy/nexora-scheduler --replicas=0
   ```
2. **Provision a fresh database** (or empty the existing one).
3. **Restore** the most recent verified backup:
   ```bash
   gpg --batch --decrypt --passphrase "$BACKUP_GPG_PASSPHRASE" \
     --output restore.dump nexora-<TS>.dump.gpg
   pg_restore --no-owner --no-privileges --dbname "$DATABASE_URL" restore.dump
   ```
4. **Confirm schema** is at head:
   ```bash
   alembic current   # must equal alembic heads
   ```
5. **Flush Redis** (stale cache/locks/sessions from before the incident):
   ```bash
   redis-cli -u "$REDIS_URL" FLUSHALL
   ```
6. **Scale back up** and watch `/readyz` / `/metrics`:
   ```bash
   kubectl -n nexora scale deploy/nexora-api --replicas=3
   kubectl -n nexora scale deploy/nexora-worker --replicas=2
   kubectl -n nexora scale deploy/nexora-scheduler --replicas=1
   ```

## Component failure playbook

| Failure | Automatic behavior | Operator action |
|---|---|---|
| **Redis down** | Cache/sessions/denylist/locks degrade to in-process fallbacks; rate-limit fails open; client auto-reconnects after cooldown (`app/redis/client.py`) | Restore Redis; no data action needed |
| **PostgreSQL failover** | `pool_pre_ping` discards dead connections; requests retry on new connection | None if HA Postgres; else restore (above) |
| **A worker crashes** | In-flight Arq job is re-queued; durable `jobs` row drives retry/DLQ | Inspect `GET /v1/jobs/dead-letter` |
| **An API pod crashes** | K8s restarts it; PDB + anti-affinity keep capacity; LB routes around it | None |
| **Scheduler pod down** | Lease expires; replacement pod resumes cron; missed ticks run next cycle | None |
| **Network partition** | Redis lock TTLs + DB `claim_due` CAS prevent duplicate scheduled execution | Heal partition |

## Chaos drills

`app/tests/test_chaos_resilience.py` exercises Redis-unavailable fallback,
circuit-breaker open/half-open recovery, bulkhead saturation, leader election and
versioned-cache invalidation in CI. Re-run after any change to the Redis layer.
