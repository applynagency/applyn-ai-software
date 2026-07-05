#!/usr/bin/env bash
# Commit pilot manifests to internal Gitea (bootstrap only).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GITEA_CID=$(docker ps -qf name=pilot-gitea)
USER="pilot-admin"
PASS="PilotGiteaInternalOnly2026!"
REPO_API="http://localhost:3000/api/v1/repos/pilot-admin/pilot-test/contents"

upload_file() {
  local path="$1"
  local dest="$2"
  local b64 content sha payload
  b64=$(base64 < "$path" | tr -d '\n')
  sha=$(docker exec "$GITEA_CID" curl -sf -u "$USER:$PASS" \
    "$REPO_API/$dest" 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("sha",""))' 2>/dev/null || echo "")
  if [ -n "$sha" ]; then
    method=PUT
    payload="{\"message\":\"Sprint 66E: update $dest\",\"content\":\"$b64\",\"sha\":\"$sha\"}"
  else
    method=POST
    payload="{\"message\":\"Sprint 66E: add $dest\",\"content\":\"$b64\"}"
  fi
  docker exec "$GITEA_CID" curl -sf -X "$method" -u "$USER:$PASS" \
    "$REPO_API/$dest" -H "Content-Type: application/json" -d "$payload" >/dev/null
}

upload_file "$ROOT/deploy/pilot-internal/k8s/infra/pilot-demo/deployment.yaml" "infra/pilot-demo/deployment.yaml"
upload_file "$ROOT/deploy/pilot-internal/k8s/infra/pilot-demo/service.yaml" "infra/pilot-demo/service.yaml"
echo "gitea_commit_complete"
