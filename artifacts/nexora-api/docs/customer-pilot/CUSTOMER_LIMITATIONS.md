# Customer Pilot Limitations

## Platform limitations

| Limitation | Detail |
|------------|--------|
| One operation | Only **one** reversible mutation per pilot enrollment (configurable limit) |
| Non-production only | Production-tier environments are blocked |
| Namespace scope | No cluster-wide or multi-namespace operations |
| Provider coverage | Kubernetes scale/restart templates only; other providers unsupported |
| No secrets access | Cannot read or mount secrets during pilot |
| No exec / port-forward | Interactive debugging not available through pilot |
| No delete | Delete operations are not in the pilot catalog |
| No cloud mutation | AWS, GCP, Azure resource changes excluded |
| No auto-remediation | Failed verification does not auto-fix without human action |
| No autonomous rollback | Rollback requires eligible verification failure, not missing evidence |

## Integration limitations

- Metrics require Prometheus-compatible query API (read-only)
- Source control is read-only; no PR merge or pipeline trigger
- Stale integrations (>24h since validation) may block launch readiness

## Evidence limitations

- `INSUFFICIENT_EVIDENCE` when collectors fail — not treated as rollout failure
- Partial metric series may block `VERIFIED` status
- Simulated execution available only in non-customer test environments

## Operational limitations

- Approval expiry invalidates pending confirmations
- Payload changes after approval invalidate the approval record
- Cross-organization access is always denied
- Kill switch blocks all operations immediately when enabled

## Unsupported actions (pilot catalog)

- Cluster upgrades, node drain, CRD changes
- Ingress, Service, or NetworkPolicy mutation
- HorizontalPodAutoscaler changes
- Certificate or secret rotation
- Database or message-queue operations

## Post-pilot

Passing the customer pilot does **not** grant:

- Production access
- Expanded RBAC
- GA warranty or SLA tier
- Unlimited operations

A separate agreement is required for production onboarding.
