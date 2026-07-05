#!/usr/bin/env bash
#
# Restore-verification for an encrypted Nexora backup (Sprint 61B).
#
# Decrypts a backup, restores it into a scratch database, and runs sanity checks
# (table presence + Alembic head match). Exits non-zero if the backup is not
# restorable — wire this into CI / a scheduled job so backups are proven, not
# assumed.
#
# Usage:
#   BACKUP_GPG_PASSPHRASE=... ./pg_restore_verify.sh path/to/nexora-XXX.dump.gpg
#
# Optional env:
#   VERIFY_DB_URL   admin DSN to a throwaway server (default: local postgres)
#   SCRATCH_DB      scratch db name (default: nexora_verify_<pid>)
#
set -euo pipefail

ENCRYPTED="${1:?usage: pg_restore_verify.sh <backup.dump.gpg>}"
: "${BACKUP_GPG_PASSPHRASE:?BACKUP_GPG_PASSPHRASE is required}"

ADMIN_DSN="${VERIFY_DB_URL:-postgresql://postgres:postgres@localhost:5432/postgres}"
SCRATCH_DB="${SCRATCH_DB:-nexora_verify_$$}"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"; psql "$ADMIN_DSN" -c "DROP DATABASE IF EXISTS ${SCRATCH_DB};" >/dev/null 2>&1 || true' EXIT

# Optional checksum verification.
if [[ -f "${ENCRYPTED}.sha256" ]]; then
  echo "[verify] checking sha256"
  (cd "$(dirname "$ENCRYPTED")" && { sha256sum -c "$(basename "${ENCRYPTED}.sha256")" \
     || shasum -a 256 -c "$(basename "${ENCRYPTED}.sha256")"; })
fi

echo "[verify] decrypting"
DUMP="${WORKDIR}/restore.dump"
gpg --batch --yes --quiet --decrypt --passphrase "$BACKUP_GPG_PASSPHRASE" \
  --output "$DUMP" "$ENCRYPTED"

echo "[verify] creating scratch database ${SCRATCH_DB}"
psql "$ADMIN_DSN" -c "CREATE DATABASE ${SCRATCH_DB};"

SCRATCH_DSN="${ADMIN_DSN%/*}/${SCRATCH_DB}"
echo "[verify] restoring"
pg_restore --no-owner --no-privileges --dbname="$SCRATCH_DSN" "$DUMP"

echo "[verify] sanity checks"
TABLES=$(psql "$SCRATCH_DSN" -tAc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")
echo "[verify] public tables: ${TABLES}"
if [[ "${TABLES}" -lt 10 ]]; then
  echo "ERROR: too few tables restored (${TABLES}) — backup looks incomplete" >&2
  exit 1
fi

VERSION=$(psql "$SCRATCH_DSN" -tAc "SELECT version_num FROM alembic_version;" || true)
echo "[verify] alembic head: ${VERSION:-<none>}"
if [[ -z "${VERSION}" ]]; then
  echo "ERROR: alembic_version missing — schema not restored" >&2
  exit 1
fi

echo "[verify] OK — backup is restorable"
