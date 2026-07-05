# Kubernetes RBAC Templates

Namespace-scoped RBAC for customer pilot onboarding. Apply in your **pilot namespace only**.

## Read-only assessment Role

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
  - apiGroups: [""]
    resources: ["pods", "events"]
    verbs: ["get", "list", "watch"]
```

## Optional scale capability (future approved pilot operation only)

Add to the same Role:

```yaml
  - apiGroups: ["apps"]
    resources: ["deployments/scale"]
    verbs: ["get", "patch", "update"]
```

## RoleBinding

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: pilot-namespace-operator
  namespace: <pilot-namespace>
subjects:
  - kind: ServiceAccount
    name: pilot-operator
    namespace: <pilot-namespace>
roleRef:
  kind: Role
  name: pilot-namespace-operator
  apiGroup: rbac.authorization.k8s.io
```

## Explicitly excluded

- `secrets` read
- `pods/exec`, `pods/portforward`
- `nodes`, `clusterroles`, `clusterrolebindings`
- `delete` or `create` on workloads
- Wildcard verbs or resources

Onboarding validation runs SelfSubjectAccessReview checks and reports gaps before any pilot operation is proposed.
