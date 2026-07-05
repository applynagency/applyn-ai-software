"""Cross-signal correlation engine (Sprint 65B)."""

from __future__ import annotations

from datetime import UTC, datetime


def build_investigation_timeline(
    *,
    metrics: list[dict] | None = None,
    logs: list[dict] | None = None,
    traces: list[dict] | None = None,
    events: list[dict] | None = None,
    alerts: list[dict] | None = None,
    deployments: list[dict] | None = None,
    incidents: list[dict] | None = None,
) -> dict:
    """Merge logs, metrics, traces, events, deployments, incidents into one timeline."""
    entries: list[dict] = []
    now = datetime.now(UTC).isoformat()

    for m in metrics or []:
        entries.append({
            "kind": "METRIC", "ts": m.get("ts", now),
            "title": m.get("name", "metric anomaly"),
            "detail": m, "source": "metrics",
        })
    for log in logs or []:
        entries.append({
            "kind": "LOG", "ts": log.get("ts", now),
            "title": str(log.get("line", ""))[:120],
            "detail": log, "source": "logs",
        })
    for t in traces or []:
        entries.append({
            "kind": "TRACE", "ts": now,
            "title": f"Trace {t.get('trace_id', '?')} — {t.get('root_service', '')}",
            "detail": t, "source": "traces",
        })
    for e in events or []:
        entries.append({
            "kind": "EVENT", "ts": e.get("event_timestamp", e.get("ts", now)),
            "title": e.get("title", e.get("event_type", "event")),
            "detail": e, "source": "events",
        })
    for a in alerts or []:
        entries.append({
            "kind": "ALERT", "ts": str(a.get("fired_at", a.get("created_at", now))),
            "title": a.get("alert_name", a.get("title", "alert")),
            "detail": a, "source": "alerts",
        })
    for d in deployments or []:
        entries.append({
            "kind": "DEPLOYMENT", "ts": str(d.get("started_at", d.get("created_at", now))),
            "title": d.get("name", "deployment"),
            "detail": d, "source": "deployments",
        })
    for inc in incidents or []:
        entries.append({
            "kind": "INCIDENT", "ts": str(inc.get("created_at", now)),
            "title": inc.get("title", "incident"),
            "detail": inc, "source": "incidents",
        })

    entries.sort(key=lambda x: str(x.get("ts", "")))
    return {
        "timeline": entries,
        "total": len(entries),
        "correlation_summary": _summarize(entries),
    }


def _summarize(entries: list[dict]) -> str:
    kinds = {e["kind"] for e in entries}
    if "DEPLOYMENT" in kinds and ("ALERT" in kinds or "INCIDENT" in kinds):
        return "Deployment followed by alert/incident — likely change-induced failure"
    if "TRACE" in kinds and "LOG" in kinds:
        return "Trace errors correlated with log entries"
    if "METRIC" in kinds and "ALERT" in kinds:
        return "Metric threshold breach correlated with firing alerts"
    return "Multi-signal investigation timeline assembled"
