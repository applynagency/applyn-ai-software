# Customer Pilot Scope

## In scope

| Dimension | Limit |
|-----------|-------|
| Environment | **One non-production** namespace (e.g. staging or development tier) |
| Cluster | **One** Kubernetes cluster, namespace-scoped access only |
| Repository | **One** source repository, **read-only** access |
| Observability | **Read-only** Prometheus-compatible metrics and Kubernetes events |
| Operations | **One reversible operation maximum** during the pilot window |
| Recommended operation | Deployment scale **1 → 2** replicas; rollback **2 → 1** if verification fails with evidence |

## Explicit exclusions

The following are **out of scope** and will not be requested or performed during the customer pilot:

- Production environments or production-tier namespaces
- Cluster-wide or cluster-admin RBAC
- Access to secrets, ConfigMaps with credentials, or sealed secrets
- `kubectl exec`, port-forward, or interactive shell access
- Delete permissions on any resource
- Cloud provider mutation (IAM, VPC, load balancers, managed databases, etc.)
- Git write access, branch protection changes, or pipeline triggers
- Automatic remediation without human approval
- Autonomous rollback without explicit operator authorization

## Control boundaries

- All mutations require **customer approval** and **typed confirmation** by an authorized operator.
- The platform records evidence before and after the operation.
- Pilot closure requires verified evidence; insufficient evidence blocks closure.

## Duration

Typical pilot window: **1–2 business days** for onboarding, one operation, verification, and closeout. Extensions require a new approval record.
