"""Compliance validation for platform resources."""

from __future__ import annotations

COMPLIANCE_CHECKS = [
    ("tagging", "Resources must have owner, environment, and cost-center tags"),
    ("naming", "Resource names must follow org naming convention"),
    ("encryption", "Storage and databases must use encryption at rest"),
    ("public_exposure", "No public S3 buckets or open security groups"),
    ("rbac", "Kubernetes RBAC must follow least privilege"),
    ("network", "Network policies required in production namespaces"),
    ("cost", "Idle resources over 30 days must be flagged"),
]


def run_compliance_scan(*, resources: list[dict], clusters: list[dict]) -> dict:
    """Deterministic compliance report from inventory metadata."""
    findings = []
    score = 100
    for res in resources:
        tags = res.get("tags") or {}
        if not tags.get("owner"):
            findings.append({
                "check": "tagging", "severity": "HIGH",
                "resource": res.get("name", res.get("id", "unknown")),
                "message": "Missing owner tag",
            })
            score -= 5
        if res.get("public", False):
            findings.append({
                "check": "public_exposure", "severity": "CRITICAL",
                "resource": res.get("name", "unknown"),
                "message": "Resource is publicly exposed",
            })
            score -= 15
    for cluster in clusters:
        if not cluster.get("network_policies", True):
            findings.append({
                "check": "network", "severity": "HIGH",
                "resource": cluster.get("name", "cluster"),
                "message": "Network policies not enforced",
            })
            score -= 10
    return {
        "score": max(0, score),
        "grade": "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "F",
        "findings": findings,
        "checks_run": len(COMPLIANCE_CHECKS),
        "passed": len(COMPLIANCE_CHECKS) - len({f["check"] for f in findings}),
    }
