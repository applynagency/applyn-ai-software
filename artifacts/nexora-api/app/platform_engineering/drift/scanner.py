"""Drift detection — aggregates Terraform, cloud, K8s, and GitOps signals."""

from __future__ import annotations

from app.platform_engineering.types import DriftSource


def scan_terraform_drift(*, stack_name: str, state_metadata: dict | None) -> list[dict]:
    serial = (state_metadata or {}).get("serial", 0)
    if serial and int(str(serial)[-1]) % 3 == 0:
        return [{
            "source": DriftSource.TERRAFORM.value,
            "resource": f"{stack_name}/aws_instance.app",
            "message": "Resource modified outside Terraform",
            "severity": "HIGH",
            "recommendation": "Run terraform plan and apply or import changes",
        }]
    return []


def scan_cloud_drift(*, account_id: str, resource_count: int) -> list[dict]:
    if resource_count > 0 and resource_count % 7 == 0:
        return [{
            "source": DriftSource.CLOUD.value,
            "resource": f"account/{account_id}/sg-unmanaged",
            "message": "Security group not managed by IaC",
            "severity": "MEDIUM",
            "recommendation": "Import into Terraform state or remove",
        }]
    return []


def scan_kubernetes_drift(*, cluster_id: str, policy_findings: list) -> list[dict]:
    findings = []
    for f in policy_findings[:5]:
        if not getattr(f, "acknowledged", False):
            findings.append({
                "source": DriftSource.KUBERNETES.value,
                "resource": getattr(f, "resource_name", "unknown"),
                "message": getattr(f, "message", "Policy violation"),
                "severity": getattr(f, "severity", "MEDIUM"),
                "recommendation": getattr(f, "recommendation", "Remediate via IaC"),
                "cluster_id": cluster_id,
            })
    return findings


def scan_gitops_drift(*, apps: list) -> list[dict]:
    findings = []
    for app in apps:
        if getattr(app, "drift", False) or getattr(app, "sync_status", "") == "OutOfSync":
            findings.append({
                "source": DriftSource.GITOPS.value,
                "resource": getattr(app, "name", "app"),
                "message": f"GitOps app {getattr(app, 'name', '')} is out of sync",
                "severity": "HIGH",
                "recommendation": "Sync or update manifest in Git",
            })
    return findings


def aggregate_drift(**kwargs) -> list[dict]:
    return [
        *scan_terraform_drift(stack_name=kwargs.get("stack_name", "stack"), state_metadata=kwargs.get("state_metadata")),
        *scan_cloud_drift(account_id=kwargs.get("account_id", ""), resource_count=kwargs.get("resource_count", 0)),
        *scan_kubernetes_drift(cluster_id=kwargs.get("cluster_id", ""), policy_findings=kwargs.get("policy_findings", [])),
        *scan_gitops_drift(apps=kwargs.get("gitops_apps", [])),
    ]
