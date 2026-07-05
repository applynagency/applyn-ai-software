# Customer Non-Production Pilot

This package describes how to run a **scoped, reversible, non-production pilot** of controlled Kubernetes operations with mandatory customer approval and typed confirmation.

## What this pilot is

- A time-boxed evaluation in **one non-production namespace** on **one cluster**
- **One repository** with read-only source-control access
- **Read-only** observability (metrics and events)
- **At most one reversible operation** (recommended: scale a deployment from 1 to 2 replicas, with rollback from 2 to 1)

## What this pilot is not

- Not production access
- Not cluster-wide permissions
- Not secrets access, exec, port-forward, or delete permissions
- Not cloud infrastructure mutation
- Not automatic remediation or autonomous rollback

## How control works

1. **Enrollment** — Your organization completes onboarding and integration validation.
2. **Read-only assessment** — Baseline evidence is captured before any change.
3. **Proposal** — The platform proposes exactly one operation; nothing executes yet.
4. **Customer approval** — A named approver records environment, change summary, rollback plan, expiry, and payload hash.
5. **Typed confirmation** — An authorized operator must type the exact resource name to execute.
6. **Verification** — Post-change evidence is collected; closure requires sufficient evidence.

**No action occurs without approval and typed confirmation.**

## Documents in this package

| Document | Purpose |
|----------|---------|
| [CUSTOMER_PILOT_SCOPE.md](./CUSTOMER_PILOT_SCOPE.md) | Boundaries and in-scope resources |
| [CUSTOMER_PREREQUISITES.md](./CUSTOMER_PREREQUISITES.md) | Technical and organizational prerequisites |
| [CUSTOMER_SECURITY_AND_RBAC.md](./CUSTOMER_SECURITY_AND_RBAC.md) | Minimum RBAC and security model |
| [CUSTOMER_APPROVAL_TEMPLATE.md](./CUSTOMER_APPROVAL_TEMPLATE.md) | Approval record template |
| [CUSTOMER_SUCCESS_CRITERIA.md](./CUSTOMER_SUCCESS_CRITERIA.md) | Success and closure criteria |
| [CUSTOMER_EVIDENCE_GUIDE.md](./CUSTOMER_EVIDENCE_GUIDE.md) | Before/after evidence requirements |
| [CUSTOMER_ROLLBACK_PLAN.md](./CUSTOMER_ROLLBACK_PLAN.md) | Rollback procedure |
| [CUSTOMER_LIMITATIONS.md](./CUSTOMER_LIMITATIONS.md) | Known limitations |
| [CUSTOMER_PILOT_CLOSEOUT_TEMPLATE.md](./CUSTOMER_PILOT_CLOSEOUT_TEMPLATE.md) | Closeout checklist |

## Launch readiness

Before scheduling a pilot window, run the read-only **Customer Launch Readiness** evaluation in Pilot Center (or `GET /v1/pilot/launch-readiness`). The evaluator returns `GO`, `NO_GO`, or `INSUFFICIENT_EVIDENCE` with remediation steps. It does not create organizations, enrollments, integrations, or operations.

## Recommended first operation

**Scale deployment replicas from 1 → 2** in the pilot namespace, with rollback **2 → 1** if verification fails with positive evidence of a bad rollout.
