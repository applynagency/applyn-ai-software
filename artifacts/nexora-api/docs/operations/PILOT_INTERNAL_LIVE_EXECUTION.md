# Sprint 66I — Internal Pilot Live Execution & Verification

Performs exactly one approved Nexora-controlled scale of `pilot-demo` (1→2 replicas) on the internal Docker pilot stack, then verifies with independent Kubernetes and Prometheus evidence.

## Prerequisites

- Sprint 66H complete (approval APPROVED, `CUSTOMER_APPROVAL` COMPLETED)
- Operation `30d98614-5fc6-4410-a28c-e65a15eeabc7` in `PENDING_CONFIRMATION`
- Internal pilot compose running (`pilot-k3s`, `pilot-prometheus`, API)
- SA kubeconfig available at `/data/sa-kubeconfig.yaml` in API container (read-only verification)

## Execute

```bash
docker compose -f docker-compose.yml -f docker-compose.pilot-internal.yml build api
docker compose -f docker-compose.yml -f docker-compose.pilot-internal.yml up -d api

# Optional: copy kubeconfig for read-only verification evidence
docker exec nexora-api-api-1 mkdir -p /data
docker cp /tmp/pilot-internal-kubeconfig.yaml nexora-api-api-1:/data/sa-kubeconfig.yaml

docker exec \
  -u 0 \
  -e PYTHONPATH=/app \
  -e PILOT_66I_ARTIFACT_DIR=/tmp/pilot-internal-live-execution \
  -e PILOT_INTERNAL_KUBECONFIG_PATH=/tmp/sa-kubeconfig.yaml \
  nexora-api-api-1 \
  python scripts/pilot_sprint66i_live_execution.py
```

Copy artifacts:

```bash
mkdir -p artifacts/pilot-internal-live-execution
docker cp nexora-api-api-1:/tmp/pilot-internal-live-execution/. artifacts/pilot-internal-live-execution/
```

## API flow (Nexora-controlled only)

1. Pre-execution gates + `execution-readiness`
2. `POST /v1/pilot/live-operations/{id}/confirmation-token`
3. `POST /v1/pilot/live-operations/{id}/confirm` with typed confirmation `pilot-demo`
4. Pilot → LiveMutationGate → `k8s_ops.execute_write` (scale)
5. Independent read-only K8s/Prometheus evidence
6. `POST /v1/pilot/live-operations/{id}/verify` with evidence bundle

## Safety boundaries

- No direct kubectl or SDK mutations from the script
- No `explicit_simulation`
- No second proposal/approval
- `COMPLETE` stage must remain PENDING
- Rollback only on verification failure via platform rollback helper

## Artifacts

`artifacts/pilot-internal-live-execution/` — report, before/after K8s/Prometheus/events, verification, audit, domain events, runbooks.
