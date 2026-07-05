# Customer Pilot Prerequisites

## Organizational

- [ ] Named **pilot sponsor** and **technical point of contact**
- [ ] Named **approver** (may differ from the operator who types confirmation)
- [ ] Agreed **maintenance window** for the single reversible operation
- [ ] Documented **rollback owner** and escalation path
- [ ] Non-production environment designated and confirmed not production

## Technical — Kubernetes

- [ ] One non-production namespace provisioned for the pilot
- [ ] One deployment suitable for scale test (recommended: 1 replica baseline)
- [ ] ServiceAccount with **namespace-scoped** RBAC (see [CUSTOMER_SECURITY_AND_RBAC.md](./CUSTOMER_SECURITY_AND_RBAC.md))
- [ ] Kubeconfig or in-cluster credentials issued to the platform integration (least privilege)
- [ ] Network path from the platform to the Kubernetes API (or approved agent)

## Technical — Source control

- [ ] One repository identified
- [ ] Read-only token or app credential with repository metadata access
- [ ] Default branch and deployment mapping documented

## Technical — Observability

- [ ] Prometheus-compatible metrics endpoint reachable (read-only)
- [ ] At least one replica-count or availability metric for the target deployment
- [ ] Event stream or audit log access for the pilot namespace (read-only)

## Platform enrollment

- [ ] Organization onboarded to the pilot program (allowlisted)
- [ ] Onboarding path started: Kubernetes + source control + metrics
- [ ] Integration validation completed (CONNECTED, live mode, fresh validation)
- [ ] Read-only assessment and baseline capture completed
- [ ] Launch readiness evaluation reviewed (`GO` or remediation plan for `NO_GO` / `INSUFFICIENT_EVIDENCE`)

## Safety settings

- [ ] Pilot kill switch understood (can halt all operations)
- [ ] Operation limit set to **1** for first pilot
- [ ] Cooldown period acknowledged between operations (if configured)
