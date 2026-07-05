# Sprint 66G — Internal Pilot Proposal & Customer Approval Readiness

Creates one **proposed** scale operation and a **PENDING** customer approval package. Does not approve, confirm, or execute.

## Prerequisites

- Sprint 66F complete (`PROPOSE_OPERATION` still PENDING, K8s scale RBAC enabled)
- Internal pilot compose running
- Non-production `DeliveryEnvironment` exists for the pilot org

## Execute

```bash
docker compose -f docker-compose.yml -f docker-compose.pilot-internal.yml build api
docker compose -f docker-compose.yml -f docker-compose.pilot-internal.yml up -d api

docker exec \
  -e PYTHONPATH=/app \
  -e PILOT_66G_ARTIFACT_DIR=/tmp/pilot-internal-proposal-approval \
  nexora-api-api-1 \
  python scripts/pilot_sprint66g_proposal_approval.py
```

Copy artifacts to host:

```bash
mkdir -p artifacts/pilot-internal-proposal-approval
docker cp nexora-api-api-1:/tmp/pilot-internal-proposal-approval/. artifacts/pilot-internal-proposal-approval/
```

## API flow (normal Pilot Center paths)

1. Preconditions: stages, kill switch, integration validation, workload 1/1
2. `POST /v1/pilot/live-operations/enable`
3. `POST /v1/pilot/live-operations` — proposes `scale_deployment` (completes `PROPOSE_OPERATION`)
4. `POST /v1/pilot/approvals` with `"approve": false` — creates **PENDING** approval only

## Safety boundaries

- Does **not** set `approve: true` or call `/confirm`
- Does **not** advance `CUSTOMER_APPROVAL`, `EXECUTE`, `VERIFY`, or `COMPLETE`
- Does **not** mutate Kubernetes or change RBAC/credentials

## Artifacts

`artifacts/pilot-internal-proposal-approval/` — report, proposal, pending approval, approval package (JSON/MD/HTML), runbooks, checklists, redaction scan.
