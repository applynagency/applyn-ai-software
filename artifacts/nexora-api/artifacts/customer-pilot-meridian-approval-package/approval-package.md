# Pilot Approval Package

**PROPOSED ONLY — NOT APPROVED — NOT EXECUTED**

Generated: 2026-07-03T04:15:07.100222+00:00

## Proposal
- Operation ID: `d1440973-a1d9-4c72-9c39-d992a08d5a97`
- Action: `scale_deployment`
- Status: `PENDING_CONFIRMATION`
- Execution label: `LIVE-ELIGIBLE / NOT EXECUTED`
- Idempotency key: `meridian-[REDACTED]-scale-2-to-3-v1`
- Payload hash: `01d4211b68133b9df33a64c43284509a60fb13ba489e4ba661228949a2c0f508`

## Pending approval
- Approval ID: `bc63be25-1fc0-4d4a-9b76-63c307e993ca`
- Status: `PENDING`
- Expires: 2026-07-04T04:15:07.082223Z
- Approver: Meridian Pilot Approver <approver@customer.example>

## Target
- Deployment: `[REDACTED]` in `[REDACTED]`
- Environment: meridian-staging-np (non-production)
- Integration: `4d106712-0035-42f7-be12-451fc4a8c665`

## Change
Meridian non-production pilot: scale deployment [REDACTED] from 2 to 3 replicas in namespace [REDACTED] (environment meridian-staging-np). Approval does not execute any change.

**Rollback:** Scale replicas from 3 back to 2 in namespace [REDACTED]

**Baseline hash:** `None`

## Maintenance window
Saturday 02:00–04:00 UTC

## Verification plan
- Kubernetes desired, ready, and available replicas = 3
- Three Ready pods with no rollout failure events in namespace
- Pod restart count does not increase unexpectedly versus before-state
- Prometheus kube_deployment_status_replicas_available query (supplemental only)

## Evidence limitations
- [REDACTED] workflow history unavailable — repository metadata only
- Prometheus namespace workload metrics unavailable — supplemental query evidence only
- Kubernetes deployment and pod evidence is the primary verification source

## Verification criteria

## Safety statements
- Approval alone does not execute any infrastructure mutation.
- A separate typed confirmation and execution step is required after approval.
- This package documents a proposed reversible scale operation only.