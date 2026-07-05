#!/usr/bin/env bash
# Start local Nexora stack and remove orphan containers from prior pilot profiles.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

log() { printf '==> %s\n' "$1"; }

log "Removing orphan containers (pilot-k3s, customer-pilot-prometheus, etc.)"
docker compose up -d --remove-orphans "$@"

log "Stack healthy check"
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8000/nexora-api/health >/dev/null 2>&1; then
    log "API ready at http://localhost:8000"
    exit 0
  fi
  sleep 2
done

docker compose logs api --tail 40
exit 1
