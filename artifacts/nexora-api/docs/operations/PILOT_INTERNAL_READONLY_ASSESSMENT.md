# Sprint 66D — Internal Read-Only Assessment & Baseline Capture

Read-only assessment and baseline capture for the internal **Nexora Pilot Test** organization after Sprint 66C live validation.

## Prerequisites

- Sprint 66C complete: CONNECT + VALIDATE stages `COMPLETED`, three live integrations.
- Internal pilot stack running (`pilot-k3s`, `pilot-prometheus`, `pilot-gitea`).
- Registry IDs and scope configured in `.env` (see `PILOT_INTERNAL_*` variables).

## Workflow

1. `POST /v1/pilot/assessment/run` — live read-only collectors (K8s, Gitea, Prometheus)
2. `POST /v1/pilot/baseline/capture` — timestamped baseline snapshot + scorecard
3. Export evidence pack and diagnostics

## Run script

```bash
docker compose build api && docker compose up -d --force-recreate api
docker run --rm --network nexora-api_default \
  -v "$(pwd):/app" -w /app -e PYTHONPATH=/app \
  nexora-api-api:latest python scripts/pilot_sprint66d_readonly_assessment.py \
  | tee artifacts/pilot-internal-readonly-assessment/report.json
```

## Stage rules

- **READ_ONLY_ASSESSMENT** — requires CONNECT + VALIDATE complete; live integrations required.
- **BASELINE_CAPTURE** — requires assessment persisted; writes `enrollment.baseline` with hash.
- Does **not** advance `PROPOSE_OPERATION` or beyond.

## Artifacts

Written under `artifacts/pilot-internal-readonly-assessment/`:

- `report.json` — stage transitions, assessment, baseline, go/no-go
- `evidence_pack.json`, `diagnostics.json`, `report.json` (export bundle)
- `assessment.md`, `redaction-check.json`
