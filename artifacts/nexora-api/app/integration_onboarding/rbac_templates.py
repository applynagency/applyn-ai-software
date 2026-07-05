"""RBAC YAML templates for customer pilot onboarding (Sprint 67A)."""

from __future__ import annotations

READ_ONLY_RULES = [
    {"apiGroups": ["apps"], "resources": ["deployments"], "verbs": ["get", "list", "watch"]},
    {"apiGroups": [""], "resources": ["pods", "events"], "verbs": ["get", "list", "watch"]},
]

SCALE_RULES = [
    {"apiGroups": ["apps"], "resources": ["deployments/scale"], "verbs": ["get", "patch", "update"]},
]


def build_rbac_role_yaml(*, namespace: str, include_scale: bool = True) -> str:
    rules = list(READ_ONLY_RULES)
    if include_scale:
        rules.extend(SCALE_RULES)
    lines = [
        "apiVersion: rbac.authorization.k8s.io/v1",
        "kind: Role",
        "metadata:",
        f"  name: pilot-namespace-operator",
        f"  namespace: {namespace}",
        "rules:",
    ]
    for rule in rules:
        lines.append(f"  - apiGroups: {rule['apiGroups']!r}")
        lines.append(f"    resources: {rule['resources']!r}")
        lines.append(f"    verbs: {rule['verbs']!r}")
    return "\n".join(lines) + "\n"


def build_rbac_rolebinding_yaml(*, namespace: str, service_account: str = "pilot-operator") -> str:
    return (
        "apiVersion: rbac.authorization.k8s.io/v1\n"
        "kind: RoleBinding\n"
        "metadata:\n"
        f"  name: pilot-namespace-operator\n"
        f"  namespace: {namespace}\n"
        "subjects:\n"
        "  - kind: ServiceAccount\n"
        f"    name: {service_account}\n"
        f"    namespace: {namespace}\n"
        "roleRef:\n"
        "  kind: Role\n"
        "  name: pilot-namespace-operator\n"
        "  apiGroup: rbac.authorization.k8s.io\n"
    )


def least_privilege_guidance(*, provider: str, namespace: str | None = None) -> dict:
    if provider == "KUBERNETES":
        ns = namespace or "<pilot-namespace>"
        return {
            "provider": provider,
            "read_only_assessment": build_rbac_role_yaml(namespace=ns, include_scale=False),
            "optional_scale_pilot": build_rbac_role_yaml(namespace=ns, include_scale=True),
            "role_binding": build_rbac_rolebinding_yaml(namespace=ns),
            "warnings": [
                "Write permissions are not requested during onboarding validation.",
                "Scale capability is optional and only for a future approved pilot operation.",
            ],
        }
    if provider in ("GITHUB", "GITHUB_ENTERPRISE", "GITEA"):
        return {
            "provider": provider,
            "recommended_scopes": ["repo:read", "read:org"] if provider != "GITEA" else ["read:repository"],
            "warnings": [
                "Do not grant write, admin, or workflow dispatch permissions for pilot onboarding.",
                "Webhook creation is not required.",
            ],
        }
    if provider == "PROMETHEUS":
        return {
            "provider": provider,
            "recommended_access": "Read-only HTTP access to /api/v1/query and /api/v1/targets",
            "warnings": [
                "Remote write, alert rule changes, and scrape config mutation are excluded.",
            ],
        }
    return {"provider": provider, "warnings": []}
