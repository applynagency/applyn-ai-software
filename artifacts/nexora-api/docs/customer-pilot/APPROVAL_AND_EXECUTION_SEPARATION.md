# Approval and Execution Separation

Customer pilot workflows deliberately separate **customer approval** from **platform operator execution**. This document explains why and how.

## Two independent gates

```
Proposal → Customer Approval → Operator Readiness Check → Typed Confirmation → Execution → Verification
```

| Step | Who | Customer portal? |
|------|-----|------------------|
| Propose operation | Platform operator | No (internal Pilot Center) |
| Customer approval | Customer admin | Yes — `/customer-pilot/approval` |
| Execution readiness | System + operator | View only — `/customer-pilot/execution` |
| Typed confirmation | Platform operator | **No** — internal only |
| Execute | Platform operator | **No** — internal only |
| Verify | Platform operator | View only — `/customer-pilot/evidence` |

## Customer approval package

When an operation is proposed, an **immutable approval package** is stored containing:

- Operation summary and scope
- Desired before/after state
- Risk level and expected impact
- Rollback plan
- Verification plan
- Payload hash and expiry

Customers must acknowledge the payload hash and rollback plan when approving.

## Invalidation

If anything material changes after approval, the approval becomes `INVALIDATED` or `EXPIRED`. Customers must review a **new** package before execution can proceed.

Triggers include payload changes, rollback plan changes, production environment selection, stale integrations, and expiry.

## Operator handoff

After `APPROVED`, internal operators use:

`GET /v1/pilot/live-operations/{id}/operator-handoff`

This endpoint is read-only and **re-runs readiness checks** at retrieval time. Status labels:

- `READY` — eligible for typed confirmation
- `BLOCKED` — cannot proceed (e.g. rejected approval, kill switch)
- `INSUFFICIENT_EVIDENCE` — missing required evidence

Customer approval alone never sets status to executable. The customer portal shows `READY_FOR_OPERATOR_CONFIRMATION` only when all read-only gates pass.

## Rejection

Rejecting an approval preserves the proposal and audit trail but **blocks** operator handoff and execution until a new approval cycle begins.

## EXECUTE stage

Customer approval completes the `CUSTOMER_APPROVAL` stage only. It does **not** complete the `EXECUTE` stage. Execution stages advance only through internal operator flows with `LiveMutationGate` enforcement.
