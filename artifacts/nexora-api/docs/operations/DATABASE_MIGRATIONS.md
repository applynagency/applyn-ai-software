# Database Migrations

The database schema is owned **exclusively by Alembic**. The application no
longer creates tables at runtime — the previous `Base.metadata.create_all()`
call has been removed from startup. Instead, startup *verifies* that the
connected database has been migrated to the latest revision and **refuses to
start** otherwise.

## TL;DR

| Scenario | Command |
| --- | --- |
| Fresh database (deploy) | `alembic upgrade head` |
| Existing DB built by the old `create_all()` | `alembic stamp 0001_baseline` |
| Check the DB is up to date (CI / ops) | `python -m app.database.migration_check` |
| Print the head revision | `python -m app.database.migration_check --head` |
| Create a new migration | `alembic revision --autogenerate -m "describe change"` |

## What changed

### Runtime `create_all()` removed

`app/main.py` no longer calls `create_tables()` during the lifespan. The
`create_tables()` / `drop_tables()` helpers in `app/database/session.py` remain
but are documented as **test-suite / local-sqlite only** — they must not be used
at runtime.

### Startup migration verification

On startup (lifespan), for non-sqlite databases, the app runs
`app.database.migration_check.verify_migrations_or_raise()`. If the database has
no `alembic_version` row, or its revision does not match the migration head, the
app raises `RuntimeError` and fails to start.

This is controlled by:

- `DB_MIGRATION_CHECK_ENABLED` (default `True`) — set `False` to disable.
- The check is **automatically skipped for sqlite** (the test suite and local
  dev create the schema directly via the ORM).

### Baseline squash

The original 76 incremental migrations (`001_organizations` …
`076_universal_discovery`) **could not build a database from scratch**:

- No migration ever created the foundational `users` / `workspaces` tables —
  they were only ever created by the runtime `create_all()`.
- Several migrations re-emitted `CREATE TYPE` for shared enums, raising
  `DuplicateObjectError` on a fresh PostgreSQL database.

They have been **squashed into a single baseline revision**, `0001_baseline`
(`alembic/versions/0001_baseline.py`). The legacy migrations are archived under
`alembic/legacy_versions/` (outside the Alembic chain, kept for reference only).

The baseline materializes the entire schema from `Base.metadata`, which
guarantees the migrated schema matches the ORM models exactly. `alembic check`
confirms **zero drift** between the models and the migrated database.

## Operational runbook

### Fresh deployment

```bash
alembic upgrade head
# starts at 0001_baseline; the app's startup check will pass
```

### Existing deployment (schema already built by the old runtime `create_all()`)

These databases already have all tables but no `alembic_version` row. Do **not**
re-run migrations (the tables already exist) — stamp the baseline:

```bash
alembic stamp 0001_baseline
```

After stamping, the startup check passes and future migrations apply normally.

### Creating new migrations going forward

Normal incremental Alembic from here on:

```bash
alembic revision --autogenerate -m "add widget table"
# review the generated file, then:
alembic upgrade head
```

`env.py` already wires `target_metadata = Base.metadata` and imports all models,
so autogenerate sees the full schema. `DATABASE_URL` is read from the
environment (it is normalised to `postgresql+asyncpg://`).

## Migration checker

`app/database/migration_check.py` exposes:

- `get_head_revision()` — latest revision from the migration scripts (no DB).
- `get_current_revision()` — revision stamped in the database.
- `check_migrations()` → `MigrationStatus(ok, current, head, detail)`.
- `verify_migrations_or_raise()` — raises unless the DB is at head (used at
  startup).

CLI (used by CI and ops):

```bash
python -m app.database.migration_check          # prints status; exit 1 if behind
python -m app.database.migration_check --head    # prints just the head revision
```

## CI validation

`.github/workflows/migrations.yml` runs on changes to `alembic/**`,
`app/models/**`, or `app/database/**`. Against a fresh PostgreSQL service it:

1. `alembic upgrade head` — migrations must apply cleanly to an empty DB.
2. `python -m app.database.migration_check` — DB must be at head.
3. `alembic check` — the ORM models must match the migrations (no missing
   migration / drift).
4. `alembic downgrade base` → `alembic upgrade head` → checker — a clean
   round-trip.

Any failure fails the build.

## Tests

`app/tests/test_migration_check.py` covers head detection from the real scripts,
single-head (no branching), the version-comparison logic (ok / behind /
unmigrated / DB error), the fail-fast verifier, and a real read of
`alembic_version` from a sqlite database.

## Files changed

| File | Change |
| --- | --- |
| `app/main.py` | Removed runtime `create_all()`; added startup migration verification |
| `app/database/migration_check.py` | New — checker library + CLI |
| `app/database/session.py` | Documented `create_tables`/`drop_tables` as test/dev-only |
| `app/core/config.py` | Added `DB_MIGRATION_CHECK_ENABLED` |
| `alembic/versions/0001_baseline.py` | New — squashed baseline schema |
| `alembic/legacy_versions/**` | Archived 76 legacy migrations (off the chain) |
| `.github/workflows/migrations.yml` | New — CI migration validation |
| `app/tests/test_migration_check.py` | New — checker tests |
