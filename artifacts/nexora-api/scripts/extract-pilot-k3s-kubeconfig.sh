#!/usr/bin/env bash
# Extract kubeconfig from pilot-k3s for Sprint 66C (internal non-production only).
set -euo pipefail
OUT="${1:-/tmp/pilot-internal-kubeconfig.yaml}"
CID=$(docker ps -qf name=pilot-k3s)
if [ -z "$CID" ]; then
  echo "pilot-k3s container not running" >&2
  exit 1
fi
docker exec "$CID" cat /etc/rancher/k3s/k3s.yaml | sed 's|https://127.0.0.1:6443|https://pilot-k3s:6443|g' > "$OUT"
echo "$OUT"
