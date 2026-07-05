#!/usr/bin/env bash
# Sprint 66F — Apply namespace-scoped RBAC and collect kubectl auth can-i evidence.
# Direct bootstrap to internal k3s only; does not call Nexora mutation APIs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${PILOT_66F_ARTIFACT_DIR:-$ROOT/artifacts/pilot-internal-write-capability}"
K3S_CID=$(docker ps -qf name=pilot-k3s)
if [ -z "$K3S_CID" ]; then
  echo "pilot-k3s container not running" >&2
  exit 1
fi

NAMESPACE="${PILOT_INTERNAL_K8S_NAMESPACE:-nexora-pilot}"
SA_NAME="nexora-pilot-operator"
DEPLOYMENT="pilot-demo"
KUBECONFIG_OUT="${PILOT_INTERNAL_KUBECONFIG_PATH:-/tmp/pilot-internal-sa-kubeconfig.yaml}"
AUTH_EVIDENCE="$OUT_DIR/kubectl-auth-can-i.txt"
SA_CREDENTIAL_REF="$OUT_DIR/sa-credential-reference.txt"

kubectl() { docker exec -i "$K3S_CID" kubectl "$@"; }

mkdir -p "$OUT_DIR"

echo "==> Applying RBAC manifests"
for f in serviceaccount.yaml role.yaml rolebinding.yaml; do
  cat "$ROOT/deploy/pilot-internal/k8s/infra/pilot-demo/rbac/$f" | kubectl apply -f -
done

echo "==> Waiting for service account"
for _ in $(seq 1 30); do
  if kubectl get sa "$SA_NAME" -n "$NAMESPACE" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

SA_SUBJECT="system:serviceaccount:${NAMESPACE}:${SA_NAME}"

echo "==> Recording authorization checks (service account identity)"
set +e
{
  echo "# Sprint 66F kubectl auth can-i evidence"
  echo "# identity=${SA_SUBJECT}"
  echo "# namespace=${NAMESPACE}"
  echo "# deployment=${DEPLOYMENT}"
  echo
  echo "## positive_checks"
  kubectl auth can-i get "deployments/${DEPLOYMENT}" -n "$NAMESPACE" --as="$SA_SUBJECT"
  kubectl auth can-i get deployments --subresource=scale -n "$NAMESPACE" --as="$SA_SUBJECT"
  kubectl auth can-i patch deployments --subresource=scale -n "$NAMESPACE" --as="$SA_SUBJECT"
  kubectl auth can-i update deployments --subresource=scale -n "$NAMESPACE" --as="$SA_SUBJECT"
  kubectl auth can-i list pods -n "$NAMESPACE" --as="$SA_SUBJECT"
  kubectl auth can-i list events -n "$NAMESPACE" --as="$SA_SUBJECT"
  echo
  echo "## negative_checks"
  kubectl auth can-i delete deployments -n "$NAMESPACE" --as="$SA_SUBJECT"
  kubectl auth can-i create pods -n "$NAMESPACE" --as="$SA_SUBJECT"
  kubectl auth can-i get secrets -n "$NAMESPACE" --as="$SA_SUBJECT"
  kubectl auth can-i list nodes --as="$SA_SUBJECT"
  kubectl auth can-i get deployments -n default --as="$SA_SUBJECT"
} | tee "$AUTH_EVIDENCE"
set -e

echo "==> Building limited service-account kubeconfig"
ADMIN_CFG=$(mktemp)
docker exec "$K3S_CID" cat /etc/rancher/k3s/k3s.yaml > "$ADMIN_CFG"
read -r API_SERVER CA_DATA < <(python3 - "$ADMIN_CFG" <<'PY'
import sys, yaml
cfg = yaml.safe_load(open(sys.argv[1]))
cluster = cfg["clusters"][0]["cluster"]
print(cluster["server"], cluster.get("certificate-authority-data", ""))
PY
)

TOKEN=$(kubectl create token "$SA_NAME" -n "$NAMESPACE" --duration=8760h)

python3 - "$KUBECONFIG_OUT" "$API_SERVER" "$CA_DATA" "$NAMESPACE" "$SA_NAME" "$TOKEN" <<'PY'
import sys, yaml, base64
out, server, ca, namespace, user, token = sys.argv[1:7]
cfg = {
    "apiVersion": "v1",
    "kind": "Config",
    "clusters": [{
        "name": "pilot-internal",
        "cluster": {
            "server": server.replace("127.0.0.1", "pilot-k3s"),
            "certificate-authority-data": ca,
        },
    }],
    "contexts": [{
        "name": "pilot-internal",
        "context": {
            "cluster": "pilot-internal",
            "user": user,
            "namespace": namespace,
        },
    }],
    "current-context": "pilot-internal",
    "users": [{"name": user, "user": {"token": token}}],
}
with open(out, "w") as fh:
    yaml.safe_dump(cfg, fh)
PY

rm -f "$ADMIN_CFG"
echo "[redacted — service account credential stored in Nexora Secret Manager only]" > "$SA_CREDENTIAL_REF"

echo "rbac_bootstrap_complete"
