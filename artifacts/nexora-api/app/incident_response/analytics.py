"""Incident analytics — MTTR, MTTA, trends (Sprint 65C)."""

from __future__ import annotations

from datetime import datetime


def compute_analytics(
    *,
    assignments: list[dict],
    incidents: list[dict],
    escalations: list[dict],
    action_items: list[dict] | None = None,
) -> dict:
    """Derive incident response KPIs from assignment and incident records."""
    mtta = _mean([a["mtta_minutes"] for a in assignments if a.get("mtta_minutes") is not None])
    mttr = _mean([a["mttr_minutes"] for a in assignments if a.get("mttr_minutes") is not None])
    by_severity: dict[str, int] = {}
    by_service: dict[str, int] = {}
    for inc in incidents:
        sev = (inc.get("severity") or "UNKNOWN").upper()
        by_severity[sev] = by_severity.get(sev, 0) + 1
        svc = inc.get("service") or inc.get("service_name") or "unknown"
        by_service[str(svc)] = by_service.get(str(svc), 0) + 1
    escalation_success = _escalation_rate(escalations, assignments)
    workload = _responder_workload(assignments)
    root_causes = _top_root_causes(incidents)
    action_completion = _action_completion(action_items or [])
    return {
        "mtta_minutes": mtta,
        "mttr_minutes": mttr,
        "open_incidents": sum(1 for i in incidents if (i.get("lifecycle_status") or "").upper() not in ("RESOLVED", "CLOSED")),
        "escalation_success_rate": escalation_success,
        "responder_workload": workload,
        "incident_trend": _trend(incidents),
        "by_severity": by_severity,
        "by_service": dict(sorted(by_service.items(), key=lambda x: -x[1])[:10]),
        "top_root_causes": root_causes,
        "action_item_completion_rate": action_completion,
    }


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def _escalation_rate(escalations: list[dict], assignments: list[dict]) -> float | None:
    if not assignments:
        return None
    acked = sum(1 for a in assignments if a.get("acknowledged_at"))
    return round(acked / len(assignments), 2) if assignments else None


def _responder_workload(assignments: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    for a in assignments:
        uid = a.get("responder_id") or a.get("owner_id")
        if uid:
            counts[str(uid)] = counts.get(str(uid), 0) + 1
    return [{"user_id": k, "incident_count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])[:10]]


def _top_root_causes(incidents: list[dict]) -> list[dict]:
    causes: dict[str, int] = {}
    for inc in incidents:
        rc = inc.get("root_cause") or inc.get("suspected_trigger")
        if rc:
            key = str(rc)[:80]
            causes[key] = causes.get(key, 0) + 1
    return [{"cause": k, "count": v} for k, v in sorted(causes.items(), key=lambda x: -x[1])[:5]]


def _action_completion(items: list[dict]) -> float | None:
    if not items:
        return None
    done = sum(1 for i in items if (i.get("status") or "").upper() in ("DONE", "COMPLETED", "CLOSED"))
    return round(done / len(items), 2)


def _trend(incidents: list[dict]) -> list[dict]:
    buckets: dict[str, int] = {}
    for inc in incidents:
        ts = inc.get("created_at")
        if isinstance(ts, datetime):
            key = ts.strftime("%Y-%m-%d")
        elif ts:
            key = str(ts)[:10]
        else:
            continue
        buckets[key] = buckets.get(key, 0) + 1
    return [{"date": k, "count": v} for k, v in sorted(buckets.items())[-14:]]
