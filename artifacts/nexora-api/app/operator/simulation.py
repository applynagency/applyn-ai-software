"""Pre-recommendation simulation — blast radius and impact estimates."""

from __future__ import annotations

from app.operator.types import RecommendationKind


def simulate_recommendation(
    *,
    kind: str,
    referenced_resources: list[dict],
    environment: str | None = None,
) -> dict:
    """Simulate impact before recommending an action."""
    blast = len(referenced_resources) or 1
    env = (environment or "UNKNOWN").upper()
    is_prod = env in ("PRODUCTION", "PROD")

    base = {
        "blast_radius_score": min(100, blast * 12),
        "dependency_count": blast,
        "deployment_impact": "LOW",
        "cost_impact_usd": 0.0,
        "slo_impact": "NEUTRAL",
        "approval_required": is_prod,
        "rollback_complexity": "LOW",
        "simulation_notes": [],
    }

    if kind == RecommendationKind.SCALE_DEPLOYMENT.value:
        base.update(deployment_impact="MEDIUM", cost_impact_usd=50.0, slo_impact="POSITIVE")
    elif kind == RecommendationKind.REDUCE_COST.value:
        base.update(deployment_impact="LOW", cost_impact_usd=-200.0, slo_impact="NEUTRAL")
    elif kind == RecommendationKind.ROTATE_CERTIFICATE.value:
        base.update(deployment_impact="HIGH", rollback_complexity="MEDIUM", approval_required=True)
    elif kind == RecommendationKind.RESTART_DEPLOYMENT.value:
        base.update(deployment_impact="HIGH" if is_prod else "MEDIUM", approval_required=is_prod)
    elif kind == RecommendationKind.OPTIMIZE_TERRAFORM.value:
        base.update(deployment_impact="MEDIUM", rollback_complexity="MEDIUM", approval_required=True)

    base["simulation_notes"].append(f"Environment: {env}")
    base["simulation_notes"].append(f"Resources affected: {blast}")
    return base
