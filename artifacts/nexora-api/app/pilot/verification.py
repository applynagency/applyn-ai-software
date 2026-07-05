"""Post-operation verification helpers (Sprint 66B/66I/66J)."""

from __future__ import annotations

from typing import Any

# Reasons that indicate evidence could not be collected — never trigger rollback.
_INSUFFICIENT_PREFIXES = (
    "source_mode_unavailable",
    "kubernetes_evidence_error",
    "kubernetes_evidence_missing",
    "prometheus_evidence_missing",
    "prometheus_evidence_error",
    "prometheus_metric_series_missing",
    "prometheus_query_failed",
    "prometheus_unavailable",
)

# Positive, evidence-backed failure signals — rollback may be evaluated.
_FAILURE_PREFIXES = (
    "kubernetes_rollout_failed",
    "kubernetes_replicas_mismatch",
    "kubernetes_warning_events",
    "kubernetes_unexpected_restart",
    "prometheus_replicas_mismatch",
    "execution_failed",
)


def collect_before_state(*, resource_name: str, environment_tier: str, params: dict | None = None) -> dict:
    return {
        "resource_name": resource_name,
        "environment_tier": environment_tier,
        "params": params or {},
        "captured": "pre_execution",
    }


def _prom_available_replicas(prometheus_evidence: dict | None) -> int | None:
    if not prometheus_evidence:
        return None
    if prometheus_evidence.get("prometheus_error"):
        return None
    status = (prometheus_evidence.get("status") or "").lower()
    if status and status not in ("success", "ok"):
        return None
    try:
        results = (prometheus_evidence.get("data") or {}).get("result") or []
        if not results:
            return None
        return int(float(results[0]["value"][1]))
    except (KeyError, TypeError, ValueError):
        return None


def _classify_reasons(reasons: list[str]) -> tuple[list[str], list[str]]:
    insufficient: list[str] = []
    failures: list[str] = []
    for reason in reasons:
        if any(reason.startswith(p) for p in _INSUFFICIENT_PREFIXES):
            insufficient.append(reason)
        elif any(reason.startswith(p) for p in _FAILURE_PREFIXES):
            failures.append(reason)
        else:
            insufficient.append(reason)
    return insufficient, failures


def is_rollback_eligible(verdict: dict) -> bool:
    """Rollback only when verification positively failed with collected evidence."""
    if verdict.get("verification_status") != "VERIFICATION_FAILED":
        return False
    if not verdict.get("evidence_backed_failure"):
        return False
    failed_rules = verdict.get("failed_verification_rules") or []
    return bool(failed_rules)


def evaluate_scale_verification(
    *,
    before: dict,
    execution_result: dict,
    kubernetes_evidence: dict | None,
    prometheus_evidence: dict | None,
    target_replicas: int,
    source_mode: str,
    events_evidence: dict | None = None,
) -> dict:
    """Require independent Kubernetes and Prometheus evidence for live scale verification."""
    if source_mode in ("OFFLINE", "UNAVAILABLE"):
        return {
            "verification_status": "INSUFFICIENT_EVIDENCE",
            "source_mode": source_mode,
            "message": "Live evidence unavailable — cannot verify operation outcome",
            "before": before,
            "after": {},
            "reasons": ["source_mode_unavailable"],
            "evidence_backed_failure": False,
            "failed_verification_rules": [],
            "rollback_eligible": False,
        }
    if source_mode == "SIMULATED" or execution_result.get("simulated"):
        return {
            "verification_status": "VERIFIED",
            "source_mode": "SIMULATED",
            "message": "Simulated execution — verification based on explicit simulation flag only",
            "before": before,
            "after": {"status": "Simulated"},
            "evidence_backed_failure": False,
            "failed_verification_rules": [],
            "rollback_eligible": False,
        }
    if execution_result.get("blocked") or execution_result.get("success") is False:
        failed_rules = ["execution_failed"]
        return {
            "verification_status": "VERIFICATION_FAILED",
            "source_mode": source_mode,
            "message": execution_result.get("message") or execution_result.get("error") or "Execution failed",
            "before": before,
            "after": {"execution": execution_result},
            "reasons": failed_rules,
            "evidence_backed_failure": True,
            "failed_verification_rules": failed_rules,
            "rollback_eligible": True,
        }

    reasons: list[str] = []
    k8s_ok = False
    prom_ok = False
    k8s_collected = False
    prom_collected = False
    after: dict[str, Any] = {"execution": execution_result}

    k8s = kubernetes_evidence or {}
    if k8s.get("kubernetes_error"):
        reasons.append(f"kubernetes_evidence_error:{k8s['kubernetes_error']}")
    elif not kubernetes_evidence:
        reasons.append("kubernetes_evidence_missing")
    else:
        k8s_collected = True
        deploy = k8s.get("deployment") or {}
        after["kubernetes"] = k8s
        desired = deploy.get("desired_replicas")
        available = deploy.get("available_replicas") or deploy.get("ready_replicas")
        pods = k8s.get("pods") or []
        ready_pods = [p for p in pods if p.get("ready")]
        warnings = k8s.get("warning_events") or []
        rollout_failed = bool(k8s.get("rollout_failed"))
        if rollout_failed:
            reasons.append("kubernetes_rollout_failed")
        elif desired == target_replicas and available == target_replicas and len(ready_pods) >= target_replicas:
            k8s_ok = True
        else:
            reasons.append(
                f"kubernetes_replicas_mismatch(desired={desired},available={available},ready_pods={len(ready_pods)})",
            )
        if warnings:
            reasons.append("kubernetes_warning_events_present")
            k8s_ok = False
        restarts = sum(p.get("restarts", 0) for p in pods)
        before_restarts = (before.get("kubernetes") or {}).get("total_restarts", 0)
        if restarts > before_restarts:
            reasons.append("kubernetes_unexpected_restart_increase")
            k8s_ok = False

    prom = prometheus_evidence or {}
    if prom.get("prometheus_error"):
        reasons.append(f"prometheus_evidence_error:{prom['prometheus_error']}")
    elif not prometheus_evidence:
        reasons.append("prometheus_evidence_missing")
    else:
        after["prometheus"] = prom
        status = (prom.get("status") or "").lower()
        if status and status not in ("success", "ok"):
            reasons.append(f"prometheus_unavailable(status={status})")
        else:
            prom_val = _prom_available_replicas(prom)
            if prom_val is None:
                results = (prom.get("data") or {}).get("result") or []
                if not results:
                    reasons.append("prometheus_metric_series_missing")
                else:
                    reasons.append("prometheus_query_failed")
            else:
                prom_collected = True
                if prom_val == target_replicas:
                    prom_ok = True
                else:
                    reasons.append(f"prometheus_replicas_mismatch(actual={prom_val},target={target_replicas})")

    if events_evidence:
        after["events"] = events_evidence

    insufficient_reasons, failure_reasons = _classify_reasons(reasons)

    if k8s_ok and prom_ok:
        after["deployment_readiness"] = "Available"
        after["status"] = "Available"
        return {
            "verification_status": "VERIFIED",
            "source_mode": source_mode,
            "message": "Live Kubernetes and Prometheus evidence confirm target replica count",
            "before": before,
            "after": after,
            "target_replicas": target_replicas,
            "evidence_backed_failure": False,
            "failed_verification_rules": [],
            "rollback_eligible": False,
        }

    if insufficient_reasons:
        return {
            "verification_status": "INSUFFICIENT_EVIDENCE",
            "source_mode": source_mode,
            "message": "Required Kubernetes and/or Prometheus evidence incomplete or unavailable",
            "before": before,
            "after": after,
            "reasons": reasons,
            "insufficient_evidence_reasons": insufficient_reasons,
            "evidence_backed_failure": False,
            "failed_verification_rules": [],
            "rollback_eligible": False,
        }

    if failure_reasons and k8s_collected and prom_collected:
        return {
            "verification_status": "VERIFICATION_FAILED",
            "source_mode": source_mode,
            "message": "Live verification failed required checks",
            "before": before,
            "after": after,
            "reasons": reasons,
            "failed_verification_rules": failure_reasons,
            "evidence_backed_failure": True,
            "rollback_eligible": True,
        }

    return {
        "verification_status": "INSUFFICIENT_EVIDENCE",
        "source_mode": source_mode,
        "message": "Required Kubernetes and/or Prometheus evidence incomplete",
        "before": before,
        "after": after,
        "reasons": reasons,
        "insufficient_evidence_reasons": insufficient_reasons or reasons,
        "evidence_backed_failure": False,
        "failed_verification_rules": [],
        "rollback_eligible": False,
    }


def evaluate_closure_evidence(
    *,
    kubernetes_evidence: dict | None,
    prometheus_evidence: dict | None,
    integration_evidence: dict | None,
    target_replicas: int,
) -> dict:
    """Read-only final closure check — all signals must be present and healthy."""
    blockers: list[str] = []
    k8s = kubernetes_evidence or {}
    if k8s.get("kubernetes_error"):
        blockers.append(f"kubernetes:{k8s['kubernetes_error']}")
    elif not kubernetes_evidence:
        blockers.append("kubernetes_evidence_missing")
    else:
        deploy = k8s.get("deployment") or {}
        desired = deploy.get("desired_replicas")
        available = deploy.get("available_replicas") or deploy.get("ready_replicas")
        ready_pods = [p for p in (k8s.get("pods") or []) if p.get("ready")]
        if desired != target_replicas or available != target_replicas:
            blockers.append(f"kubernetes_replicas(desired={desired},available={available})")
        if len(ready_pods) != target_replicas:
            blockers.append(f"kubernetes_ready_pods={len(ready_pods)}")

    prom_val = _prom_available_replicas(prometheus_evidence)
    if prom_val is None:
        if prometheus_evidence and prometheus_evidence.get("prometheus_error"):
            blockers.append(f"prometheus:{prometheus_evidence['prometheus_error']}")
        else:
            blockers.append("prometheus_metric_unavailable")
    elif prom_val != target_replicas:
        blockers.append(f"prometheus_replicas={prom_val}")

    integration = integration_evidence or {}
    state = (integration.get("lifecycle_state") or integration.get("state") or "").upper()
    mode = (integration.get("provider_mode") or "").lower()
    if state != "CONNECTED":
        blockers.append(f"integration_state={state or 'unknown'}")
    if mode and mode != "live":
        blockers.append(f"integration_mode={mode}")

    return {
        "closure_ready": not blockers,
        "blockers": blockers,
        "verification_status": "VERIFIED" if not blockers else "INSUFFICIENT_EVIDENCE",
    }


def evaluate_verification(
    *,
    before: dict,
    after: dict,
    execution_result: dict,
    source_mode: str,
) -> dict:
    """Never report success without evidence. Simulated ops are explicitly labeled."""
    if source_mode in ("OFFLINE", "UNAVAILABLE"):
        return {
            "verification_status": "INSUFFICIENT_EVIDENCE",
            "source_mode": source_mode,
            "message": "Live evidence unavailable — cannot verify operation outcome",
            "before": before,
            "after": after,
            "evidence_backed_failure": False,
            "failed_verification_rules": [],
            "rollback_eligible": False,
        }
    if source_mode == "SIMULATED" or execution_result.get("simulated"):
        return {
            "verification_status": "VERIFIED",
            "source_mode": "SIMULATED",
            "message": "Simulated execution — verification based on explicit simulation flag only",
            "before": before,
            "after": after,
            "evidence_backed_failure": False,
            "failed_verification_rules": [],
            "rollback_eligible": False,
        }
    post = after.get("deployment_readiness") or after.get("status")
    pre = before.get("deployment_readiness") or before.get("status")
    if post is None:
        return {
            "verification_status": "INSUFFICIENT_EVIDENCE",
            "source_mode": source_mode,
            "message": "Post-operation state missing",
            "before": before,
            "after": after,
            "evidence_backed_failure": False,
            "failed_verification_rules": [],
            "rollback_eligible": False,
        }
    healthy = post in ("Available", "Ready", "Succeeded", "Healthy", True)
    status = "VERIFIED" if healthy else "VERIFICATION_FAILED"
    failed_rules = [] if healthy else ["deployment_readiness_failed"]
    return {
        "verification_status": status,
        "source_mode": source_mode,
        "message": "Live post-operation check completed",
        "before": before,
        "after": after,
        "readiness_changed": pre != post,
        "evidence_backed_failure": not healthy,
        "failed_verification_rules": failed_rules,
        "rollback_eligible": not healthy,
    }


def merge_after_state(execution_result: dict, integration_signals: dict | None = None) -> dict:
    after: dict[str, Any] = {"execution": execution_result}
    if integration_signals:
        after["observability"] = integration_signals
    if execution_result.get("simulated"):
        after["status"] = "Simulated"
        after["deployment_readiness"] = "Simulated"
    elif execution_result.get("blocked"):
        after["status"] = "Blocked"
    else:
        after["status"] = execution_result.get("status", "PendingVerification")
    return after
