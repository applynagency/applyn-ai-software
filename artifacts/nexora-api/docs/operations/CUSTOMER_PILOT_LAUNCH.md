# Customer Pilot Launch (Operations)

## Overview

This runbook covers launching a **scoped customer non-production pilot** using the customer launch pack and read-only launch readiness evaluator. It does **not** connect customer infrastructure automatically.

## Pre-launch checklist (operations)

1. Confirm deployment has `PILOT_MODE_ENABLED=true`
2. Add customer organization to `PILOT_ORGANIZATION_IDS` (or use explicit onboarding workflow)
3. Share `docs/customer-pilot/` package with customer (no internal IDs or hostnames)
4. Customer completes [CUSTOMER_PREREQUISITES.md](../customer-pilot/CUSTOMER_PREREQUISITES.md)
5. Customer provisions namespace-scoped RBAC per [CUSTOMER_SECURITY_AND_RBAC.md](../customer-pilot/CUSTOMER_SECURITY_AND_RBAC.md)

## Launch readiness evaluation

**Read-only** — creates no organization, enrollment, integration, credential, operation, or approval.

```
GET /v1/pilot/launch-readiness
```

Or use **Customer Launch Readiness** in Pilot Center.

### Verdicts

| Verdict | Meaning |
|---------|---------|
| `GO` | All required checks passed |
| `NO_GO` | Failed checks with remediation steps |
| `INSUFFICIENT_EVIDENCE` | Missing enrollment, integrations, or RBAC evidence |

### Evaluated dimensions

- Pilot feature gating
- Organization allowlisting
- Enrollment safety (kill switch, operation limit)
- Integration lifecycle/mode/capabilities/freshness (K8s, GitHub, Prometheus)
- Non-production environment declaration
- Minimum RBAC evidence
- Approval and support contacts
- Backup/restore readiness acknowledgment

## Customer onboarding flow

1. Customer organization created through standard onboarding (not by readiness evaluator)
2. Start onboarding path: `POST /v1/pilot/onboarding-paths/k8s-github-prometheus/start`
3. Customer connects integrations (operations team assists; no auto-mutation)
4. Run readiness check and assessment (read-only)
5. Capture baseline
6. Review launch readiness until `GO` or remediated

## First operation (recommended)

Per [CUSTOMER_PILOT_SCOPE.md](../customer-pilot/CUSTOMER_PILOT_SCOPE.md):

- **Scale deployment 1 → 2** in pilot namespace
- Rollback **2 → 1** only on `VERIFICATION_FAILED` with evidence

Requires:

1. Proposal (`POST /v1/pilot/live-operations`)
2. Customer approval (`POST /v1/pilot/approvals` + decide if pending)
3. Typed confirmation (`POST .../confirm`)
4. Verification (`POST .../verify`)

## Closeout

Customer completes [CUSTOMER_PILOT_CLOSEOUT_TEMPLATE.md](../customer-pilot/CUSTOMER_PILOT_CLOSEOUT_TEMPLATE.md).

Platform closure gate (`POST /v1/pilot/closure`) requires verified evidence — insufficient evidence blocks COMPLETE stage.

## Explicit prohibitions during customer pilot setup

- No customer credentials stored without customer authorization
- No Kubernetes/cloud/GitHub/Prometheus mutation from operations scripts
- No pilot operation execution during readiness-only evaluation
- No marking platform GA-ready based on pilot pass alone

## Support escalation

| Issue | Action |
|-------|--------|
| `INSUFFICIENT_EVIDENCE` at verify | Fix collector RBAC; do not rollback |
| `NO_GO` launch readiness | Follow `remediation_steps` in response |
| Payload hash invalidation | Re-propose and re-approve |
| Kill switch enabled | Disable only after incident review |

## Related documents

- [PILOT_RELIABILITY_HARDENING.md](./PILOT_RELIABILITY_HARDENING.md)
- [PILOT_INTERNAL_CLOSURE.md](./PILOT_INTERNAL_CLOSURE.md) (internal pilot — closed)
- `docs/customer-pilot/` — customer-facing package
