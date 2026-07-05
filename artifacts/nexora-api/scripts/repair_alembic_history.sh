#!/usr/bin/env bash
# Repair Alembic history for databases with schema but no alembic_version row.
# Does NOT drop data. Run from artifacts/nexora-api with db/redis available.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://nexora:nexora@localhost:5432/nexora}"

log() { printf '\n==> %s\n' "$1"; }

log "Auditing schema drift"
python3 scripts/audit_schema_drift.py || true

log "Stamping Alembic to 023_backend_code_review (schema through backend code review)"
alembic stamp 023_backend_code_review

log "Applying reconciliation migration"
alembic upgrade head

log "Verifying Alembic head"
alembic current

log "Alembic repair complete"
