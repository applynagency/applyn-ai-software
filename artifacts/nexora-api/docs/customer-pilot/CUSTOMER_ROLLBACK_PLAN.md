# Customer Rollback Plan

## When rollback applies

Rollback reverses the **single pilot operation** when verification returns **`VERIFICATION_FAILED`** with positive, evidence-backed failure (e.g. replica mismatch, failed rollout).

Rollback does **not** apply when:

- Verification is **`INSUFFICIENT_EVIDENCE`** (missing or incomplete collectors)
- Operation was cancelled before execution
- No mutation occurred

## Recommended rollback for scale pilot

| Step | Action |
|------|--------|
| 1 | Confirm verification status is `VERIFICATION_FAILED` with documented rules |
| 2 | Authorized operator authorizes rollback per approval record |
| 3 | Scale deployment from **2 → 1** replica in pilot namespace |
| 4 | Re-collect Kubernetes and metrics evidence |
| 5 | Confirm 1/1 replicas healthy before closeout |

## Rollback for restart pilot

If the approved operation was `restart_deployment`:

- Rollback is **operational**, not automatic — redeploy previous revision or scale to known-good state per your runbook
- Document the recovery action in closeout

## Preconditions

- [ ] Rollback plan referenced in approval record
- [ ] Namespace-scoped RBAC includes `deployments/scale` patch
- [ ] Operator available during maintenance window

## Communication

| Audience | Notification |
|----------|--------------|
| Approver | Rollback initiated and outcome |
| Support contact | If rollback fails or evidence remains insufficient |
| Stakeholders | Pilot paused; no further operations without new approval |

## Failure of rollback

If rollback cannot complete:

1. Stop pilot operations (kill switch if needed)
2. Execute manual recovery per your internal runbook
3. Do not attempt additional platform operations without new approval
4. Document incident in closeout template

## No autonomous rollback

The platform does not roll back without explicit authorization paths tied to verified failure evidence. Insufficient evidence never triggers silent rollback.
