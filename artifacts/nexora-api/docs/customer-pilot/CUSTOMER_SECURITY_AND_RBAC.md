# Customer Security and RBAC

## Principles

- **Namespace-scoped only** — no cluster-admin, no cross-namespace access
- **Least privilege** — read for assessment; write limited to one scale/restart action
- **No secrets** — ServiceAccount must not read Secret resources
- **Auditable** — all API calls attributable to a dedicated ServiceAccount

## Minimum RBAC (namespace-scoped)

Grant the pilot ServiceAccount these verbs on resources **within the pilot namespace only**:

| API group | Resource | Verbs |
|-----------|----------|-------|
| `apps` | `deployments` | `get`, `list`, `watch` |
| `apps` | `deployments/scale` | `get`, `patch`, `update` |
| `""` (core) | `pods` | `get`, `list`, `watch` |
| `""` (core) | `events` | `get`, `list`, `watch` |

### Example Role (illustrative)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pilot-namespace-operator
  namespace: <pilot-namespace>
rules:
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments/scale"]
    verbs: ["get", "patch", "update"]
  - apiGroups: [""]
    resources: ["pods", "events"]
    verbs: ["get", "list", "watch"]
```

Bind with a `RoleBinding` to a dedicated ServiceAccount in the same namespace.

## Explicitly denied

- `secrets`, `clusterroles`, `clusterrolebindings`
- `delete` on any resource
- `pods/exec`, `pods/portforward`
- `nodes`, `namespaces`, cluster-scoped resources
- Cloud provider APIs

## Credential handling

- Credentials are stored encrypted and scoped to your organization
- Credentials are used only for validated integration operations
- Export and evidence packs redact tokens, kubeconfig bodies, and API keys

## Human access model

| Role | Responsibility |
|------|----------------|
| Approver | Records approval with environment, change, rollback, expiry |
| Operator | Types exact resource name to confirm execution |
| Observer | Read-only access to pilot status and evidence |

Approval and typed confirmation may be performed by different individuals per your policy.
