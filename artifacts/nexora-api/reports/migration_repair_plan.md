# APPYLN Emergency Recovery — Migration Repair Plan

## Situation (pre-recovery)

| Symptom | Cause |
|---------|-------|
| `column workspaces.organization_id does not exist` | Schema created outside Alembic; partial manual DDL |
| `relation "organizations" already exists` on `alembic upgrade` | Tables present but `alembic_version` missing or stale |
| API startup failure in `backfill_organization_data` | ORM expects columns migrations never applied |

## Current state (post-recovery)

| Check | Status |
|-------|--------|
| `alembic_version` table | Present |
| Current revision | `024_schema_reconciliation` |
| Head revision | `024_schema_reconciliation` |
| `workspaces.organization_id` | Present (nullable, indexed, FK) |
| `alembic upgrade head` | Idempotent — no-op when at head |
| `GET /nexora-api/health` | 200 |

## Repair strategy (no data destruction)

### Step 1 — Audit

```bash
python scripts/audit_schema_drift.py
```

Compares live PostgreSQL schema against expected Alembic head state.

### Step 2 — Stamp (only if tables exist but `alembic_version` is empty)

**Do not run on empty database.**

```bash
# Only when all tables through 023 exist but alembic_version is missing:
alembic stamp 023_backend_code_review
```

### Step 3 — Reconciliation migration

Migration `024_schema_reconciliation` is **idempotent**:

- Adds `workspaces.organization_id` only if missing
- Creates index `ix_workspaces_organization_id` only if missing
- Creates FK `fk_workspaces_organization_id` only if missing

```bash
alembic upgrade head
```

### Step 4 — Verify API startup

```bash
docker compose up -d api
curl -fsS http://localhost:8000/nexora-api/health
```

## Rollback

`024_schema_reconciliation` downgrade removes only the reconciliation artifacts (column/index/FK) if they were added by that migration. **Do not downgrade in production** unless explicitly rolling back tenancy linkage.

## Fresh environment bootstrap

For CI or new developers (no production data):

```bash
docker compose up -d db redis
alembic upgrade head
docker compose up -d api
```

## Ongoing guardrails

1. Never create tables manually in shared environments
2. Always run `alembic upgrade head` before starting API
3. Use `scripts/audit_schema_drift.py` in verification pipeline
4. Rebuild Docker image after code changes (`docker compose build api`)
