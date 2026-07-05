"""Guided pilot onboarding paths (Sprint 66A)."""

from __future__ import annotations

PILOT_ONBOARDING_PATHS: dict[str, dict] = {
    "k8s-github-prometheus": {
        "id": "k8s-github-prometheus",
        "name": "Kubernetes + GitHub + Prometheus",
        "prerequisites": [
            "Kubernetes cluster with API access",
            "GitHub personal access token or GitHub App with repo read scope",
            "Prometheus HTTP API endpoint reachable from Nexora",
        ],
        "integrations": [
            {"provider": "KUBERNETES", "resource_type": "kubernetes"},
            {"provider": "GITHUB", "resource_type": "marketplace"},
            {"provider": "PROMETHEUS", "resource_type": "observability"},
        ],
        "required_capabilities": ["kubernetes.read", "source.repositories.read", "observability.metrics.query"],
    },
    "k8s-github-argocd-prometheus": {
        "id": "k8s-github-argocd-prometheus",
        "name": "Kubernetes + GitHub + Argo CD + Prometheus",
        "prerequisites": [
            "Kubernetes cluster with API access",
            "GitHub token with repository access",
            "Argo CD API endpoint and token",
            "Prometheus HTTP API endpoint",
        ],
        "integrations": [
            {"provider": "KUBERNETES", "resource_type": "kubernetes"},
            {"provider": "GITHUB", "resource_type": "marketplace"},
            {"provider": "ARGOCD", "resource_type": "marketplace"},
            {"provider": "PROMETHEUS", "resource_type": "observability"},
        ],
        "required_capabilities": [
            "kubernetes.read", "source.repositories.read", "gitops.sync", "observability.metrics.query",
        ],
    },
    "aws-eks-github-cloudwatch": {
        "id": "aws-eks-github-cloudwatch",
        "name": "AWS + EKS + GitHub Actions + CloudWatch",
        "prerequisites": [
            "AWS IAM credentials with EKS/CloudWatch read access",
            "EKS kubeconfig",
            "GitHub token for Actions visibility",
        ],
        "integrations": [
            {"provider": "AWS", "resource_type": "marketplace"},
            {"provider": "KUBERNETES", "resource_type": "kubernetes"},
            {"provider": "GITHUB", "resource_type": "marketplace"},
            {"provider": "CLOUDWATCH", "resource_type": "observability"},
        ],
        "required_capabilities": ["cloud.resources.write", "kubernetes.read", "observability.metrics.query"],
    },
    "azure-aks-devops-monitor": {
        "id": "azure-aks-devops-monitor",
        "name": "Azure + AKS + Azure DevOps + Azure Monitor",
        "prerequisites": [
            "Azure service principal with subscription access",
            "AKS kubeconfig",
            "Azure DevOps PAT with pipeline read",
            "Azure Monitor query access",
        ],
        "integrations": [
            {"provider": "AZURE", "resource_type": "marketplace"},
            {"provider": "KUBERNETES", "resource_type": "kubernetes"},
            {"provider": "AZURE_DEVOPS", "resource_type": "marketplace"},
            {"provider": "AZURE_MONITOR", "resource_type": "observability"},
        ],
        "required_capabilities": ["cloud.resources.write", "kubernetes.read", "observability.metrics.query"],
    },
}

PILOT_CHECKLIST_TEMPLATE: list[dict] = [
    {"section": "organization", "item_key": "org_created", "title": "Organization created and admin assigned"},
    {"section": "organization", "item_key": "license_valid", "title": "Subscription/license valid"},
    {"section": "security", "item_key": "roles_configured", "title": "Required roles and permissions configured"},
    {"section": "security", "item_key": "mfa_enabled", "title": "MFA enabled for privileged users"},
    {"section": "platform", "item_key": "audit_healthy", "title": "Audit logging healthy"},
    {"section": "platform", "item_key": "backup_verified", "title": "Backup and restore verification complete"},
    {"section": "integrations", "item_key": "readiness_enabled", "title": "Integration readiness enabled"},
    {"section": "integrations", "item_key": "integration_connected", "title": "At least one integration connected"},
    {"section": "integrations", "item_key": "capabilities_validated", "title": "Required capabilities validated"},
    {"section": "notifications", "item_key": "channels_configured", "title": "Notification channels configured"},
    {"section": "incident", "item_key": "oncall_configured", "title": "On-call/escalation policy configured"},
    {"section": "delivery", "item_key": "production_tagged", "title": "Production environment tagged"},
    {"section": "delivery", "item_key": "approval_policy", "title": "Approval policy configured"},
    {"section": "delivery", "item_key": "rollback_documented", "title": "Rollback strategy documented"},
    {"section": "support", "item_key": "contacts_configured", "title": "Support and escalation contacts configured"},
    {"section": "compliance", "item_key": "retention_reviewed", "title": "Data retention / privacy settings reviewed"},
]

PILOT_TROUBLESHOOTING: dict[str, str] = {
    "invalid_kubeconfig": "Verify kubeconfig server URL, CA bundle, and client credentials. Re-validate after updating the secret reference.",
    "expired_token": "Rotate the API token in your secret manager and re-validate the connection.",
    "insufficient_k8s_rbac": "Grant get/list/watch on workloads; for pilot live ops grant patch/update on deployments in the target namespace.",
    "github_repo_access": "Ensure the token or GitHub App has repository contents read and Actions read for required repos.",
    "prometheus_unreachable": "Confirm Prometheus URL is reachable from Nexora and /api/v1/query returns 200.",
    "argocd_permissions": "Token needs application get/list; sync requires additional apply permissions.",
    "cloud_identity_denied": "Verify IAM role/subscription scope includes read for inventory and monitoring.",
    "observability_query": "Grant metrics/logs query capability on the observability integration.",
}
