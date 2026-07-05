"""Cluster health scoring (Sprint 65A)."""

from __future__ import annotations


def compute_health_score(
    *,
    node_count: int,
    unhealthy_pods: int,
    total_pods: int,
    pending_ops: int,
    policy_findings: int,
) -> dict:
    """Derive a 0-100 cluster health score from inventory signals."""
    pod_ratio = 1.0 - (unhealthy_pods / max(total_pods, 1))
    node_factor = 1.0 if node_count > 0 else 0.5
    policy_penalty = min(30, policy_findings * 3)
    ops_penalty = min(15, pending_ops * 2)
    score = max(0, min(100, int(pod_ratio * 70 * node_factor + 30 - policy_penalty - ops_penalty)))
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"
    return {
        "score": score,
        "grade": grade,
        "unhealthy_pods": unhealthy_pods,
        "total_pods": total_pods,
        "policy_findings": policy_findings,
        "pending_operations": pending_ops,
    }
