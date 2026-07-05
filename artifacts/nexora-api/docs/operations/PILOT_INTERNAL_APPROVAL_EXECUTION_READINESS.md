# Sprint 66H — Internal Pilot Approval & Execution-Readiness Dry Run

**APPROVED FOR INTERNAL PILOT — NOT EXECUTED — TYPED CONFIRMATION REQUIRED**

Approves the single existing PENDING customer approval from Sprint 66G through the normal
`POST /v1/pilot/approvals/{id}/decide` workflow, advances only `CUSTOMER_APPROVAL`, and runs a
read-only execution-readiness dry run. Does **not** confirm, execute, or mutate Kubernetes.

## Prerequisites

- Sprint 66G complete (one proposal, one PENDING approval)
- Approval ID `9cbd4673-d64b-4ef2-a0d7-510483366be3` still PENDING and unexpired
- Internal pilot compose running (`docker-compose.pilot-internal.yml`)
- `pilot-demo` at 1/1 replica in `nexora-pilot`

## Execute

```bash
docker compose -f docker-compose.yml -f docker-compose.pilot-internal.yml build api
docker compose -f docker-compose.yml -f docker-compose.pilot-internal.yml up -d api

docker exec \
  -e PYTHONPATH=/app \
  -e PILOT_66H_ARTIFACT_DIR=/tmp/pilot-internal-approval-execution-readiness \
  nexora-api-api-1 \
  python scripts/pilot_sprint66h_approval_execution_readiness.py
```

Copy artifacts to host:

```bash
mkdir -p artifacts/pilot-internal-approval-execution-readiness
docker cp nexora-api-api-1:/tmp/pilot-internal-approval-execution-readiness/. \
  artifacts/pilot-internal-approval-execution-readiness/
```

## API flow

1. Pre-decision validation: approval PENDING, hash match, integration live, workload 1/1
2. `POST /v1/pilot/approvals/{approval_id}/decide` with `approve: true` and rationale
3. `POST /v1/pilot/live-operations/{operation_id}/execution-readiness` (read-only gates)
4. Post-validation: replicas unchanged, `operation_count` zero, no confirm audit

## Safety boundaries

- Does **not** call `/confirm` or submit typed confirmation
- Does **not** advance `EXECUTE`, `VERIFY`, or `COMPLETE`
- Does **not** mutate Kubernetes, RBAC, credentials, or kill switch
- Does **not** create a second proposal or approval
- Stops **NO-GO** if approval is expired (no extension)

## Artifacts

`artifacts/pilot-internal-approval-execution-readiness/` — report, pre/post readonly evidence,
approval decision, execution-readiness result, stage status, audit evidence, runbooks, redaction scan.
