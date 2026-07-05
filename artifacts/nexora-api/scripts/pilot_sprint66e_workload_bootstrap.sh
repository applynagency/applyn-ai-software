#!/usr/bin/env bash
# Sprint 66E — Bootstrap disposable pilot workload (direct infrastructure only).
# Does NOT call Nexora Pilot Center mutation APIs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
K3S_CID=$(docker ps -qf name=pilot-k3s)
if [ -z "$K3S_CID" ]; then
  echo "pilot-k3s container not running" >&2
  exit 1
fi

kubectl() { docker exec -i "$K3S_CID" kubectl "$@"; }

echo "==> Applying kube-state-metrics"
cat "$ROOT/deploy/pilot-internal/k8s/kube-state-metrics.yaml" | kubectl apply -f -
echo "==> Applying pilot-demo workload"
cat "$ROOT/deploy/pilot-internal/k8s/infra/pilot-demo/deployment.yaml" | kubectl apply -f -
cat "$ROOT/deploy/pilot-internal/k8s/infra/pilot-demo/service.yaml" | kubectl apply -f -

echo "==> Waiting for pilot-demo rollout"
kubectl rollout status deployment/pilot-demo -n nexora-pilot --timeout=120s
kubectl rollout status deployment/kube-state-metrics -n kube-system --timeout=120s

echo "==> Reloading Prometheus config"
docker compose -f "$ROOT/docker-compose.yml" -f "$ROOT/docker-compose.pilot-internal.yml" up -d pilot-prometheus
sleep 3
docker exec nexora-api-pilot-prometheus-1 wget -q -O- --post-data='' http://localhost:9090/-/reload >/dev/null || true

echo "==> Workload status"
kubectl get deploy,po,svc -n nexora-pilot -l app=pilot-demo -o wide
kubectl get svc -n kube-system kube-state-metrics -o wide

echo "bootstrap_complete"
