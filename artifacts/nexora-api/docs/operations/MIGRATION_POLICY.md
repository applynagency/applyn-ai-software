# Migration Policy

Alembic owns the Nexora database schema. Application startup verifies the database is at the latest head revision.

## Supported upgrade path

```
alembic upgrade head
```

Current head: `0034_pilot_readiness`

## Irreversible migration boundary

Revision `0013_converge_graph` permanently retires the legacy service-dependency graph and migrates topology into the Platform Knowledge Graph.

**Downgrade below `0013_converge_graph` is not supported.** Earlier convergence migrations (`0009`–`0012`) are also irreversible.

### Supported downgrade / re-upgrade path (production)

```
alembic upgrade head
alembic downgrade 0013_converge_graph
alembic upgrade head
```

This is the maximum supported rollback using Alembic alone.

### Rollback below the irreversible boundary

Do **not** use `alembic downgrade base` in production. Restore from a database backup taken before the migration instead.

## PostgreSQL validation

Run against the Docker Compose `db` service:

```bash
docker compose up -d db

docker compose run --rm --no-deps \
  -e NEXORA_POSTGRES_MIGRATION_TEST=1 \
  -e DATABASE_URL=postgresql+asyncpg://nexora:nexora@db:5432/nexora \
  -e REDIS_URL="" \
  -e RATE_LIMIT_ENABLED=false \
  api \
  python -m pytest app/tests/test_postgres_migration_chain.py -q
```

## Production migration requirements

1. Take a full database backup before applying migrations.
2. Run `alembic upgrade head` in a maintenance window.
3. Verify `alembic current` shows `0034_pilot_readiness`.
4. Run application startup migration check (`app.database.migration_check`).
5. If rollback is required after crossing `0013_converge_graph`, restore the backup — do not downgrade below the irreversible boundary.

## Boolean column defaults

Migrations from `0026_operator` onward use `sa.true()` / `sa.false()` for PostgreSQL-compatible boolean defaults. Integer literals (`DEFAULT 1`) are not valid on PostgreSQL boolean columns.
