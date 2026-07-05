"""Alert intelligence — grouping, suppression, storm detection (Sprint 65B)."""

from __future__ import annotations


def analyze_alerts(alerts: list[dict]) -> dict:
    """Group alerts, detect storms, recommend thresholds."""
    if not alerts:
        return {"groups": [], "storms": [], "recommendations": []}

    by_corr: dict[str, list] = {}
    by_service: dict[str, list] = {}
    for a in alerts:
        cid = a.get("correlation_id") or a.get("labels", {}).get("correlation_id") or "ungrouped"
        by_corr.setdefault(str(cid), []).append(a)
        svc = a.get("service") or a.get("labels", {}).get("service") or "unknown"
        by_service.setdefault(str(svc), []).append(a)

    groups = [
        {"correlation_id": cid, "count": len(items), "alerts": items[:5], "severity": _max_severity(items)}
        for cid, items in by_corr.items()
    ]
    storms = [
        {"service": svc, "count": len(items), "severity": _max_severity(items)}
        for svc, items in by_service.items() if len(items) >= 3
    ]
    recommendations = []
    if storms:
        recommendations.append({"action": "MERGE_ALERTS", "reason": f"{len(storms)} alert storm(s) detected"})
    dup_names = _duplicate_names(alerts)
    if dup_names:
        recommendations.append({"action": "SUPPRESS_DUPLICATES", "alerts": dup_names[:5]})
    for storm in storms[:3]:
        recommendations.append({
            "action": "ADJUST_THRESHOLD",
            "service": storm["service"],
            "suggestion": f"Raise threshold for {storm['service']} — {storm['count']} alerts in window",
        })

    return {
        "groups": groups,
        "storms": storms,
        "recommendations": recommendations,
        "duplicate_count": len(dup_names),
    }


def _max_severity(alerts: list[dict]) -> str:
    order = {"CRITICAL": 3, "HIGH": 2, "WARNING": 1, "INFO": 0}
    best = "INFO"
    for a in alerts:
        sev = (a.get("severity") or "WARNING").upper()
        if order.get(sev, 0) > order.get(best, 0):
            best = sev
    return best


def _duplicate_names(alerts: list[dict]) -> list[str]:
    seen: dict[str, int] = {}
    for a in alerts:
        name = a.get("alert_name") or a.get("title") or ""
        seen[name] = seen.get(name, 0) + 1
    return [n for n, c in seen.items() if c > 1 and n]
