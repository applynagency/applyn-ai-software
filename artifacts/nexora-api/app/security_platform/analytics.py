"""Security analytics and posture scoring (Sprint 65D)."""

from __future__ import annotations


def compute_posture(*, findings: list[dict], snapshots: list[dict] | None = None) -> dict:
    by_severity: dict[str, int] = {}
    by_source: dict[str, int] = {}
    open_critical = 0
    for f in findings:
        sev = (f.get("severity") or "INFO").upper()
        src = (f.get("source") or "UNKNOWN").upper()
        by_severity[sev] = by_severity.get(sev, 0) + 1
        by_source[src] = by_source.get(src, 0) + 1
        if sev == "CRITICAL" and (f.get("status") or "OPEN").upper() in ("OPEN", "ACKNOWLEDGED", "IN_REMEDIATION"):
            open_critical += 1
    score = max(0, 100 - open_critical * 15 - by_severity.get("HIGH", 0) * 5 - by_severity.get("MEDIUM", 0) * 2)
    sla_breaches = sum(1 for f in findings if f.get("sla_breached"))
    return {
        "posture_score": score,
        "grade": "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "F",
        "open_critical": open_critical,
        "by_severity": by_severity,
        "by_source": by_source,
        "sla_breaches": sla_breaches,
        "trend": snapshots or [],
    }
