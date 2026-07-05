"""Operational reasoning — detect patterns from aggregated platform signals."""

from __future__ import annotations

from app.operator.types import RecommendationKind


def analyze_signals(*, queue_items: list[dict], dashboard: dict, kpis: dict, drift: list, cost: dict) -> list[dict]:
    """Produce reasoning findings from composed platform data (no duplicate engines)."""
    findings: list[dict] = []

    failed_deploys = [q for q in queue_items if q.get("type") == "DEPLOYMENT"]
    if len(failed_deploys) >= 2:
        findings.append({
            "kind": "RECURRING_FAILURE",
            "severity": "HIGH",
            "title": f"{len(failed_deploys)} failed deployments need attention",
            "recommendation_kind": RecommendationKind.RESTART_DEPLOYMENT.value,
            "evidence": failed_deploys[:5],
        })

    failed_pipelines = [q for q in queue_items if q.get("type") == "FAILED_WORKFLOW"]
    if len(failed_pipelines) >= 3:
        findings.append({
            "kind": "SLOW_PIPELINES",
            "severity": "MEDIUM",
            "title": "Multiple pipeline failures detected",
            "recommendation_kind": RecommendationKind.IMPROVE_PIPELINE.value,
            "evidence": failed_pipelines[:5],
        })

    drift_count = len(drift) if drift else dashboard.get("active_drift", 0)
    if drift_count > 0:
        findings.append({
            "kind": "CONFIGURATION_DRIFT",
            "severity": "HIGH",
            "title": f"{drift_count} drift findings require remediation",
            "recommendation_kind": RecommendationKind.OPTIMIZE_TERRAFORM.value,
            "evidence": drift[:3] if isinstance(drift, list) else [],
        })

    if cost.get("waste_estimate") and cost["waste_estimate"] > 100:
        findings.append({
            "kind": "RESOURCE_WASTE",
            "severity": "MEDIUM",
            "title": f"Estimated waste ${cost['waste_estimate']:.0f}/month",
            "recommendation_kind": RecommendationKind.REDUCE_COST.value,
            "evidence": [{"waste": cost["waste_estimate"], "idle": cost.get("idle_resources", 0)}],
            "estimated_savings": cost["waste_estimate"],
        })

    pending = dashboard.get("pending_approvals", 0)
    if pending >= 5:
        findings.append({
            "kind": "DEPLOYMENT_BOTTLENECK",
            "severity": "MEDIUM",
            "title": f"{pending} items awaiting approval",
            "recommendation_kind": RecommendationKind.MERGE_ALERTS.value,
            "evidence": [{"pending_approvals": pending}],
        })

    cert_findings = [q for q in queue_items if "cert" in str(q.get("title", "")).lower()]
    if cert_findings:
        findings.append({
            "kind": "CERTIFICATE_EXPIRY",
            "severity": "HIGH",
            "title": "Certificates approaching expiry",
            "recommendation_kind": RecommendationKind.ROTATE_CERTIFICATE.value,
            "evidence": cert_findings[:3],
        })

    if kpis.get("change_failure_rate_percent") and kpis["change_failure_rate_percent"] > 15:
        findings.append({
            "kind": "RISKY_DEPLOYMENTS",
            "severity": "HIGH",
            "title": f"Change failure rate {kpis['change_failure_rate_percent']}%",
            "recommendation_kind": RecommendationKind.SCALE_DEPLOYMENT.value,
            "evidence": [{"change_failure_rate": kpis["change_failure_rate_percent"]}],
        })

    return findings


def predict_issues(findings: list[dict]) -> list[dict]:
    """Lightweight prediction layer over current findings."""
    predictions = []
    for f in findings:
        if f.get("kind") in ("RECURRING_FAILURE", "RISKY_DEPLOYMENTS"):
            predictions.append({
                "prediction": "Incident likely within 24h if unaddressed",
                "confidence": 0.72,
                "based_on": f["kind"],
            })
        elif f.get("kind") == "RESOURCE_WASTE":
            predictions.append({
                "prediction": "Cost overrun projected next billing cycle",
                "confidence": 0.65,
                "based_on": f["kind"],
            })
    return predictions
