# Sprint 66C — Internal Live Integration Validation

Read-only validation of Kubernetes, GitHub, and Prometheus for the internal **Nexora Pilot Test** organization. No mutations, no pilot live operations, no `explicit_simulation`.

## Prerequisites

- Pilot Environment Activation complete (`PILOT_MODE_ENABLED`, org allowlist, enrollment safety limits).
- Internal non-production credentials only (never production).
- `SSRF_ALLOW_PRIVATE_NETWORKS=true` in `.env` when using the ephemeral Docker pilot stack.
- Ephemeral stack: `docker compose -f docker-compose.yml -f docker-compose.pilot-internal.yml up -d pilot-prometheus pilot-k3s pilot-gitea`

## Required credentials

| Variable | Purpose |
|----------|---------|
| `PILOT_INTERNAL_GITHUB_TOKEN` | Read-only token for one internal pilot repository |
| `PILOT_INTERNAL_GITHUB_REPO` | Repository scope label (e.g. `pilot-admin/pilot-test`) |
| `PILOT_INTERNAL_GITHUB_BASE_URL` | Internal Gitea API base (e.g. `http://pilot-gitea:3000/api/v1`) |
| `PILOT_INTERNAL_KUBECONFIG_PATH` | Non-production kubeconfig (SA limited to pilot namespace) |
| `PILOT_INTERNAL_PROMETHEUS_ENDPOINT` | Read-only Prometheus HTTP API (default `http://pilot-prometheus:9090`) |
| `PILOT_INTERNAL_K8S_NAMESPACE` | Pilot namespace label (default `nexora-pilot`) |

Extract k3s kubeconfig after `pilot-k3s` is healthy:

```bash
./scripts/extract-pilot-k3s-kubeconfig.sh /tmp/pilot-internal-kubeconfig.yaml
export PILOT_INTERNAL_KUBECONFIG_PATH=/tmp/pilot-internal-kubeconfig.yaml
```

Bootstrap internal Gitea (non-production GitHub-compatible API):

```bash
./scripts/bootstrap-pilot-gitea.sh /tmp/pilot-internal-gitea
source /tmp/pilot-internal-gitea/credentials.env
```

## Run validation

```bash
docker run --rm --network nexora-api_default \
  -v "$(pwd):/app" -w /app -e PYTHONPATH=/app \
  -e PILOT_INTERNAL_GITHUB_TOKEN -e PILOT_INTERNAL_GITHUB_REPO \
  -e PILOT_INTERNAL_KUBECONFIG_PATH -e PILOT_INTERNAL_PROMETHEUS_ENDPOINT \
  nexora-api-api:latest python scripts/pilot_sprint66c_live_validation.py \
  | tee artifacts/pilot-internal-live-validation/report.json
```

Artifacts are written under `artifacts/pilot-internal-live-validation/` (report, dashboard, readiness, evidence pack, redaction check).

## Stage rules

- **CONNECT** advanced only after all three integrations are registered.
- **VALIDATE** advanced only if all three are `lifecycle_state=CONNECTED` and `provider_mode=live`.
- Stops with `NO_GO` if any provider is `FAILED`, `DEGRADED`, `REAUTH_REQUIRED`, `OFFLINE`, or `UNAVAILABLE`.

## Go / no-go

| Decision | Condition |
|----------|-----------|
| **GO** | All three providers live + CONNECT/VALIDATE stages advanced |
| **NO_GO** | Any provider missing, not live, or redaction failure |

Next step after **GO**: `READ_ONLY_ASSESSMENT` only (Sprint 66C does not include assessment execution).
