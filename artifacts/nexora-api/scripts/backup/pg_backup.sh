#!/usr/bin/env bash
#
# Automated, encrypted PostgreSQL backup with retention (Sprint 61B).
#
# Produces a compressed pg_dump custom-format archive, encrypts it with GPG
# (symmetric, AES-256) and prunes backups older than the retention window.
# Designed to run as a Kubernetes CronJob or host cron entry.
#
# Required env:
#   DATABASE_URL            postgres DSN (postgresql[+asyncpg]://user:pass@host:port/db)
#   BACKUP_GPG_PASSPHRASE   passphrase used to encrypt the archive
# Optional env:
#   BACKUP_DIR              output dir            (default: /backups)
#   BACKUP_RETENTION_DAYS   prune older than N    (default: 14)
#   BACKUP_S3_BUCKET        if set, aws s3 cp the encrypted file there
#
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL is required" >&2
  exit 1
fi
if [[ -z "${BACKUP_GPG_PASSPHRASE:-}" ]]; then
  echo "ERROR: BACKUP_GPG_PASSPHRASE is required (encrypted backups are mandatory)" >&2
  exit 1
fi

# Normalize the SQLAlchemy async DSN to a libpq-compatible one for pg_dump.
PG_DSN="${DATABASE_URL/+asyncpg/}"
PG_DSN="${PG_DSN/+psycopg2/}"

mkdir -p "$BACKUP_DIR"
ARCHIVE="${BACKUP_DIR}/nexora-${TIMESTAMP}.dump"
ENCRYPTED="${ARCHIVE}.gpg"

echo "[backup] dumping database -> ${ARCHIVE}"
pg_dump --format=custom --no-owner --no-privileges --compress=9 \
  --dbname="$PG_DSN" --file="$ARCHIVE"

echo "[backup] encrypting -> ${ENCRYPTED}"
gpg --batch --yes --symmetric --cipher-algo AES256 \
  --passphrase "$BACKUP_GPG_PASSPHRASE" \
  --output "$ENCRYPTED" "$ARCHIVE"
rm -f "$ARCHIVE"

# Integrity marker: sha256 of the encrypted artifact.
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$ENCRYPTED" > "${ENCRYPTED}.sha256"
else
  shasum -a 256 "$ENCRYPTED" > "${ENCRYPTED}.sha256"
fi

if [[ -n "${BACKUP_S3_BUCKET:-}" ]]; then
  echo "[backup] uploading to s3://${BACKUP_S3_BUCKET}/"
  aws s3 cp "$ENCRYPTED" "s3://${BACKUP_S3_BUCKET}/$(basename "$ENCRYPTED")"
  aws s3 cp "${ENCRYPTED}.sha256" "s3://${BACKUP_S3_BUCKET}/$(basename "${ENCRYPTED}.sha256")"
fi

echo "[backup] pruning backups older than ${RETENTION_DAYS} days"
find "$BACKUP_DIR" -name 'nexora-*.dump.gpg*' -type f -mtime "+${RETENTION_DAYS}" -print -delete || true

echo "[backup] done: ${ENCRYPTED}"
