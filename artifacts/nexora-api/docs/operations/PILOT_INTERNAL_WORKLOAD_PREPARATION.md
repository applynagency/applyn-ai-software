# Sprint 66E — Internal Pilot Workload Preparation

Prepares a disposable non-production workload in `nexora-pilot` for future reversible pilot operations.

## Bootstrap (direct infrastructure — not Nexora)

```bash
./scripts/pilot_sprint66e_workload_bootstrap.sh
./scripts/pilot_sprint66e_gitea_commit.sh
```

Deploys:
- `pilot-demo` Deployment + ClusterIP Service (`hashicorp/http-echo:0.2.3`, 1 replica)
- `kube-state-metrics` (NodePort `30801`) for namespace workload metrics
- Prometheus scrape config reload

Manifests: `deploy/pilot-internal/k8s/infra/pilot-demo/`  
Gitea path: `infra/pilot-demo/deployment.yaml`, `infra/pilot-demo/service.yaml`

## Nexora read-only reassessment

```bash
docker run --rm --network nexora-api_default \
  -v "$(pwd):/app" -w /app -e PYTHONPATH=/app \
  nexora-api-api:latest python scripts/pilot_sprint66e_reassessment.py
```

Calls only:
- `POST /v1/pilot/assessment/run`
- `POST /v1/pilot/baseline/refresh` (preserves prior baseline in `history`)
- `GET /v1/integrations/connections/{k8s}/capabilities`

Does **not** advance `PROPOSE_OPERATION` or later stages.

## Artifacts

`artifacts/pilot-internal-workload-preparation/report.json`
