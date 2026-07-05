# Pilot Approval Package

**PROPOSED ONLY — NOT APPROVED — NOT EXECUTED**

Generated: 2026-07-02T10:24:12.706921+00:00

## Proposal
- Operation ID: `30d98614-5fc6-4410-a28c-e65a15eeabc7`
- Action: `scale_deployment`
- Status: `PENDING_CONFIRMATION`
- Execution label: `LIVE-ELIGIBLE / NOT EXECUTED`
- Idempotency key: `sprint66g-pilot-demo-scale-1-to-2-v1`
- Payload hash: `5d69df027a2f5038e26f295678194ef0570d39440a74482ee1ea80c6dcbbb11e`

## Pending approval
- Approval ID: `9cbd4673-d64b-4ef2-a0d7-510483366be3`
- Status: `PENDING`
- Expires: 2026-07-03T10:24:12.697604Z
- Approver: Internal Pilot Approver <pilot-approver@nexora.internal>

## Target
- Deployment: `pilot-demo` in `nexora-pilot`
- Environment: development (non-production)
- Integration: `bf7ec5b8-04c2-40a3-8bb9-2d5e4077f8c8`

## Change
Controlled internal pilot validation: scale deployment pilot-demo from 1 to 2 replicas in namespace nexora-pilot (non-production) using namespace-scoped Kubernetes RBAC.

**Rollback:** Scale replicas from 2 back to 1 in namespace nexora-pilot

**Baseline hash:** `3a069634725200a94f276fd7085e70f2b20fadc862404dd639a1e01d348efcfa`

## Verification criteria
- deployment desired replicas = 2
- available replicas = 2
- both pods Ready
- no warning events attributable to the operation
- restart count does not increase unexpectedly
- Prometheus deployment available replicas query returns 2

## Safety statements
- Approval alone does not execute any infrastructure mutation.
- A separate typed confirmation and execution step is required after approval.
- This package documents a proposed reversible scale operation only.