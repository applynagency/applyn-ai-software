"""Security investigation timeline — correlates findings with incidents/deployments."""

from __future__ import annotations

from datetime import UTC, datetime


def build_security_timeline(
    *,
    findings: list[dict] | None = None,
    alerts: list[dict] | None = None,
    deployments: list[dict] | None = None,
    incidents: list[dict] | None = None,
    identities: list[dict] | None = None,
) -> dict:
    now = datetime.now(UTC).isoformat()
    entries = []
    for f in findings or []:
        entries.append({
            "kind": "FINDING", "ts": f.get("created_at", now),
            "title": f.get("title", "finding"), "severity": f.get("severity"),
            "detail": f,
        })
    for a in alerts or []:
        entries.append({
            "kind": "ALERT", "ts": str(a.get("fired_at", now)),
            "title": a.get("alert_name", "alert"), "detail": a,
        })
    for d in deployments or []:
        entries.append({
            "kind": "DEPLOYMENT", "ts": str(d.get("started_at", now)),
            "title": d.get("name", "deployment"), "detail": d,
        })
    for i in incidents or []:
        entries.append({
            "kind": "INCIDENT", "ts": str(i.get("created_at", now)),
            "title": i.get("title", "incident"), "detail": i,
        })
    for ident in identities or []:
        entries.append({
            "kind": "IDENTITY", "ts": now,
            "title": ident.get("title", "identity risk"), "detail": ident,
        })
    entries.sort(key=lambda e: str(e.get("ts", "")))
    critical = [e for e in entries if (e.get("severity") or e.get("detail", {}).get("severity")) == "CRITICAL"]
    return {
        "timeline": entries,
        "total": len(entries),
        "critical_count": len(critical),
        "summary": _summarize(entries),
    }


def _summarize(entries: list[dict]) -> str:
    kinds = {e["kind"] for e in entries}
    if "FINDING" in kinds and "DEPLOYMENT" in kinds:
        return "Security findings correlated with recent deployment — investigate change window"
    if "FINDING" in kinds and "INCIDENT" in kinds:
        return "Security findings linked to active incident"
    if critical := [e for e in entries if e.get("severity") == "CRITICAL"]:
        return f"{len(critical)} critical security signals in investigation window"
    return "Security investigation timeline assembled from org-scoped evidence"
