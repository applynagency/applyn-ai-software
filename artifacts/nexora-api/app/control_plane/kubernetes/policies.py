"""Cluster policy scanner — warn only, never auto-mutate."""

from __future__ import annotations

from dataclasses import dataclass

from app.control_plane.kubernetes.base import DiscoveredResource


@dataclass
class PolicyFinding:
    policy: str
    severity: str
    resource_kind: str
    resource_name: str
    namespace: str | None
    message: str
    recommendation: str


def scan_policies(resources: list[DiscoveredResource]) -> list[PolicyFinding]:
    findings: list[PolicyFinding] = []
    for r in resources:
        if r.kind == "Pod":
            meta = r.metadata or {}
            if meta.get("privileged"):
                findings.append(PolicyFinding(
                    "privileged_containers", "HIGH", r.kind, r.name, r.namespace,
                    "Pod may run privileged containers",
                    "Set securityContext.privileged=false",
                ))
            if meta.get("host_network"):
                findings.append(PolicyFinding(
                    "host_networking", "HIGH", r.kind, r.name, r.namespace,
                    "Pod uses host networking",
                    "Disable hostNetwork unless required",
                ))
        if r.kind == "Deployment":
            labels = r.labels or {}
            for c in (r.metadata or {}).get("containers", []):
                image = c.get("image", "")
                if image.endswith(":latest") or ":" not in image:
                    findings.append(PolicyFinding(
                        "latest_tag", "MEDIUM", r.kind, r.name, r.namespace,
                        f"Container image uses latest tag: {image}",
                        "Pin images to immutable digests or version tags",
                    ))
                if not c.get("resources", {}).get("limits"):
                    findings.append(PolicyFinding(
                        "missing_limits", "MEDIUM", r.kind, r.name, r.namespace,
                        f"Container {c.get('name')} missing resource limits",
                        "Set requests and limits for CPU/memory",
                    ))
                if not c.get("livenessProbe") or not c.get("readinessProbe"):
                    findings.append(PolicyFinding(
                        "missing_probes", "LOW", r.kind, r.name, r.namespace,
                        f"Container {c.get('name')} missing health probes",
                        "Add liveness and readiness probes",
                    ))
        if r.kind == "Service":
            stype = (r.metadata or {}).get("type")
            if stype == "LoadBalancer":
                findings.append(PolicyFinding(
                    "public_service", "MEDIUM", r.kind, r.name, r.namespace,
                    "Service exposed via LoadBalancer",
                    "Review public exposure and restrict with network policies",
                ))
        if r.kind == "ClusterRoleBinding":
            subjects = (r.metadata or {}).get("subjects", 0)
            if subjects:
                findings.append(PolicyFinding(
                    "cluster_admin_bindings", "HIGH", r.kind, r.name, r.namespace,
                    "ClusterRoleBinding grants cluster-wide permissions",
                    "Audit bindings and prefer namespace-scoped roles",
                ))
    return findings
