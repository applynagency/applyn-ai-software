# Sprint 66F — Internal Pilot Write Capability Enablement

Enables namespace-scoped Kubernetes RBAC for `pilot-demo` scale operations in the internal pilot stack only.

## Prerequisites

- Internal pilot compose running (`docker-compose.pilot-internal.yml`)
- Pilot stages through `BASELINE_CAPTURE` completed; `PROPOSE_OPERATION` still pending

## Bootstrap (direct infrastructure — not Nexora mutations)

```bash
./scripts/pilot_sprint66f_rbac_bootstrap.sh
./scripts/pilot_sprint66f_gitea_commit.sh
```

RBAC manifests live under `deploy/pilot-internal/k8s/infra/pilot-demo/rbac/` and are committed to Gitea `pilot-admin/pilot-test` at `infra/pilot-demo/rbac/`.

## Nexora revalidation and preflight (read-only + preflight only)

```bash
# Copy SA credential into API container (bootstrap step generates host path separately)
docker cp /tmp/pilot-internal-kubeconfig.yaml nexora-api-api-1:/data/sa-kubeconfig.yaml
docker exec -u root nexora-api-api-1 chown appuser:appuser /data/sa-kubeconfig.yaml

docker exec \
  -e PYTHONPATH=/app \
  -e PILOT_INTERNAL_KUBECONFIG_PATH=/data/sa-kubeconfig.yaml \
  -e PILOT_66F_ARTIFACT_DIR=/tmp/pilot-internal-write-capability \
  nexora-api-api-1 \
  python scripts/pilot_sprint66f_write_capability.py
```

Artifacts: `artifacts/pilot-internal-write-capability/`

## Safety boundaries

- Does **not** advance pilot stages
- Does **not** create proposals, approvals, or execute operations
- Does **not** use `explicit_simulation`
- GitHub and Prometheus credentials unchanged
