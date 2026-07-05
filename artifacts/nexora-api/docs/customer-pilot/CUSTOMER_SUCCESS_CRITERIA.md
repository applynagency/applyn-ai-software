# Customer Success Criteria

## Pilot objectives

1. Validate read-only integration connectivity (Kubernetes, repository, metrics)
2. Complete baseline evidence capture without mutation
3. Execute **one** approved, confirmed, reversible operation
4. Verify post-change health with dual signals (Kubernetes + metrics)
5. Close the pilot with documented evidence

## Success indicators

| Criterion | Target |
|-----------|--------|
| Integrations | Kubernetes, source control, and metrics **CONNECTED** in live read-only mode |
| Assessment | Read-only assessment **completed** with no blockers |
| Baseline | Baseline capture **completed** before proposal |
| Approval | Customer approval **APPROVED** with valid payload hash |
| Execution | Operation **SUCCEEDED** after typed confirmation |
| Verification | Status **VERIFIED** with replica count and metric alignment |
| Safety | No unauthorized mutations; kill switch available throughout |
| Rollback | Rollback plan documented; rollback only if verification fails with positive evidence |

## Closure conditions

The pilot may be closed when:

- [ ] All prerequisite stages through **VERIFY** are completed
- [ ] The single operation is **VERIFIED** (or explicitly cancelled with no mutation)
- [ ] Evidence pack exported and retained by customer
- [ ] Closeout checklist completed ([CUSTOMER_PILOT_CLOSEOUT_TEMPLATE.md](./CUSTOMER_PILOT_CLOSEOUT_TEMPLATE.md))
- [ ] Customer sponsor acknowledges pilot outcome

## Non-success outcomes

| Outcome | Meaning |
|---------|---------|
| `INSUFFICIENT_EVIDENCE` | Collectors unavailable — **no rollback** triggered automatically |
| `VERIFICATION_FAILED` | Evidence shows unhealthy rollout — rollback **may** be authorized per plan |
| `BLOCKED` | Safety gate prevented execution — investigate and re-propose if needed |
| `NO_GO` (launch readiness) | Prerequisites not met — remediate before scheduling |

## What success does not mean

- **Not** general availability (GA) of the platform
- **Not** approval for production use
- **Not** expanded RBAC or additional operations without a new pilot cycle
