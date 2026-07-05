"""AI Incident Coordinator — grouping, assignment, severity (Sprint 65C)."""

from __future__ import annotations


def coordinate_incident(
    *,
    incidents: list[dict],
    alerts: list[dict],
    oncall_users: list[dict],
    service_health: list[dict] | None = None,
) -> dict:
    """Recommend grouping, responders, severity, and communications from evidence."""
    groups = _group_incidents(incidents, alerts)
    severity = _estimate_severity(incidents, alerts, service_health or [])
    responders = _recommend_responders(oncall_users, incidents)
    impact = _predict_impact(incidents, service_health or [])
    return {
        "groups": groups,
        "recommended_severity": severity,
        "recommended_responders": responders,
        "predicted_impact": impact,
        "suggested_communications": _suggest_comms(severity, impact),
        "suggested_rollback": _suggest_rollback(incidents),
        "timeline_draft": _timeline_draft(incidents, alerts),
        "postmortem_outline": _postmortem_outline(incidents),
    }


def _group_incidents(incidents: list[dict], alerts: list[dict]) -> list[dict]:
    by_service: dict[str, list] = {}
    for inc in incidents:
        svc = inc.get("service") or inc.get("service_name") or "platform"
        by_service.setdefault(str(svc), []).append(inc)
    for alert in alerts:
        svc = alert.get("service") or "platform"
        by_service.setdefault(str(svc), []).append({"kind": "alert", **alert})
    return [
        {"service": svc, "count": len(items), "incidents": items[:5]}
        for svc, items in by_service.items() if len(items) > 1
    ]


def _estimate_severity(incidents: list[dict], alerts: list[dict], health: list[dict]) -> str:
    critical_alerts = sum(1 for a in alerts if (a.get("severity") or "").upper() == "CRITICAL")
    if critical_alerts >= 3:
        return "CRITICAL"
    degraded = sum(1 for h in health if (h.get("health_score") or 100) < 50)
    if degraded:
        return "HIGH"
    if incidents:
        return (incidents[0].get("severity") or "MEDIUM").upper()
    return "MEDIUM"


def _recommend_responders(oncall: list[dict], incidents: list[dict]) -> list[dict]:
    if not oncall:
        return []
    primary = oncall[0]
    return [{
        "user_id": primary.get("user_id"),
        "name": primary.get("name", "On-call"),
        "role": "PRIMARY",
        "reason": "Current on-call for affected service",
    }]


def _predict_impact(incidents: list[dict], health: list[dict]) -> dict:
    services = {inc.get("service") or inc.get("service_name") for inc in incidents}
    services.discard(None)
    low_health = [h for h in health if (h.get("health_score") or 100) < 70]
    return {
        "affected_services": list(services)[:10],
        "degraded_services": [h.get("name") for h in low_health[:5]],
        "customer_facing_risk": len(low_health) > 0 or len(services) > 2,
    }


def _suggest_comms(severity: str, impact: dict) -> list[dict]:
    comms = [{"kind": "INTERNAL", "template": "incident_update_internal", "urgency": severity}]
    if impact.get("customer_facing_risk"):
        comms.append({"kind": "CUSTOMER", "template": "incident_status_customer", "urgency": severity})
    if severity == "CRITICAL":
        comms.append({"kind": "EXECUTIVE", "template": "incident_executive_brief", "urgency": "HIGH"})
    return comms


def _suggest_rollback(incidents: list[dict]) -> dict | None:
    for inc in incidents:
        if inc.get("triggering_change") or inc.get("recent_deployment"):
            return {"action": "ROLLBACK", "reason": "Recent deployment correlated with incident onset"}
    return None


def _timeline_draft(incidents: list[dict], alerts: list[dict]) -> list[dict]:
    entries = []
    for inc in incidents[:5]:
        entries.append({
            "ts": str(inc.get("created_at", "")),
            "kind": "INCIDENT",
            "title": inc.get("title", "Incident opened"),
        })
    for alert in alerts[:5]:
        entries.append({
            "ts": str(alert.get("fired_at", alert.get("last_seen_at", ""))),
            "kind": "ALERT",
            "title": alert.get("alert_name", "Alert"),
        })
    entries.sort(key=lambda e: e.get("ts", ""))
    return entries


def _postmortem_outline(incidents: list[dict]) -> dict:
    if not incidents:
        return {"sections": ["Summary", "Timeline", "Root Cause", "Action Items"]}
    inc = incidents[0]
    return {
        "title": f"Postmortem — {inc.get('title', 'Incident')}",
        "sections": ["Executive Summary", "Impact", "Timeline", "Root Cause", "Lessons Learned", "Action Items"],
        "draft_root_cause": inc.get("root_cause") or "Pending investigation",
    }
