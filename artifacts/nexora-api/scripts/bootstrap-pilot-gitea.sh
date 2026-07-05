#!/usr/bin/env bash
# Bootstrap internal non-production Gitea for Sprint 66C GitHub validation.
set -euo pipefail

CID=$(docker ps -qf name=pilot-gitea)
if [ -z "$CID" ]; then
  echo "pilot-gitea container not running" >&2
  exit 1
fi

OUT_DIR="${1:-/tmp/pilot-internal-gitea}"
mkdir -p "$OUT_DIR"

USER_NAME="pilot-admin"
USER_PASS="PilotGiteaInternalOnly2026!"
REPO_OWNER="pilot-admin"
REPO_NAME="pilot-test"
TOKEN_NAME="pilot-66c-readonly"

for _ in $(seq 1 30); do
  if docker exec "$CID" curl -sf http://localhost:3000/api/healthz >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! docker exec -u git "$CID" gitea admin user list 2>/dev/null | grep -q "$USER_NAME"; then
  docker exec -u git "$CID" gitea admin user create \
    --username "$USER_NAME" \
    --password "$USER_PASS" \
    --email "pilot-gitea-admin@example.com" \
    --must-change-password=false \
    --admin=false
fi

if [ -f "$OUT_DIR/credentials.env" ]; then
  # Reuse existing token when bootstrap is re-run.
  # shellcheck disable=SC1090
  source "$OUT_DIR/credentials.env"
  TOKEN="${PILOT_INTERNAL_GITHUB_TOKEN:-}"
fi

if [ -z "${TOKEN:-}" ]; then
  docker exec -u git "$CID" gitea admin user delete-access-token \
    --username "$USER_NAME" \
    --token "$TOKEN_NAME" >/dev/null 2>&1 || true
  TOKEN=$(docker exec -u git "$CID" gitea admin user generate-access-token \
    --username "$USER_NAME" \
    --token-name "$TOKEN_NAME" \
    --scopes "read:user,read:repository" \
    --raw 2>/dev/null | tail -1)
fi

if [ -z "$TOKEN" ]; then
  echo "failed to generate gitea access token" >&2
  exit 1
fi

# Create user-scoped pilot repository via API (read-only validation scope).
docker exec "$CID" curl -sf -X POST "http://localhost:3000/api/v1/user/repos" \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$REPO_NAME\",\"private\":true,\"auto_init\":true}" >/dev/null 2>&1 || true

cat > "$OUT_DIR/credentials.env" <<EOF
PILOT_INTERNAL_GITHUB_TOKEN=$TOKEN
PILOT_INTERNAL_GITHUB_REPO=$REPO_OWNER/$REPO_NAME
PILOT_INTERNAL_GITHUB_BASE_URL=http://pilot-gitea:3000/api/v1
EOF

echo "$OUT_DIR/credentials.env"
