"""Sprint 40B — Alert Correlation & Incident Timeline Engine.

Pure, side-effect-free correlation logic that sits on top of Sprint 40A:

  1. Collect read-only, timestamped events from each connected provider and
     normalize them into a single chronological series.
  2. Classify each event (change / failure / alert / degradation).
  3. Correlate: find the first change, failure, alert, and degradation, and the
     gaps between them.
  4. Score confidence (0–100) and name the suspected triggering change.

Event collection is investigation-only and read-only. When a real, verified
credential is attached the connector would supply live event timestamps; when
no live integration is configured the engine reconstructs a deterministic,
customer-safe event series from the providers the agent can read (mirroring the
39B/40A "simulated when not configured" philosophy). No secrets are ever read,
logged, or stored.
"""

from __future__ import annotations

from datetime import datetime, timedelta

# Event-type taxonomy used for change correlation.
CHANGE_TYPES = {
    "deployment", "release", "commit", "merge", "revision",
    "rollout", "workflow_run", "deployment_event",
}
FAILURE_TYPES = {"pod_restart", "crashloop", "failed_pod", "error_spike"}
ALERT_TYPES = {"monitor_alert", "incident", "dashboard_alert", "alarm", "firing"}
DEGRADATION_TYPES = {"latency_spike", "cpu_spike", "memory_spike", "saturation"}

_SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}

# Deterministic, read-only reconstruction templates per provider. Each entry is
# (event_type, title, description, severity, offset_minutes). Offsets tell the
# incident story: a change, then a rollout/restart, then degradation, then
# alerts. Only providers the agent can actually read contribute events.
_PROVIDER_EVENTS: dict[str, list[tuple]] = {
    "GITHUB": [
        ("deployment", "GitHub deployment completed", "A deployment to production finished.", "INFO", 0.0),
        ("workflow_run", "CI workflow run finished", "Post-deploy CI workflow completed.", "INFO", 1.0),
        ("release", "Release published", "A new release was published.", "INFO", 0.5),
    ],
    "JENKINS": [
        ("build_started", "Jenkins build started", "A CI pipeline build was triggered.", "INFO", 0.0),
        ("build_failed", "Jenkins build failed", "A Jenkins pipeline build failed.", "HIGH", 1.0),
    ],
    "AZURE": [
        ("revision", "Container app revision activated", "A new container app revision became active.", "INFO", 0.5),
        ("deployment_event", "Azure deployment event", "Resource deployment event recorded.", "INFO", 1.0),
    ],
    "AWS": [
        ("deployment_event", "ECS service deployment", "An ECS service deployment was registered.", "INFO", 0.5),
        ("alarm", "CloudWatch alarm triggered", "A CloudWatch alarm transitioned to ALARM.", "CRITICAL", 6.0),
    ],
    "KUBERNETES": [
        ("rollout", "Deployment rollout started", "A Kubernetes deployment rollout began.", "INFO", 2.0),
        ("pod_restart", "Pod restart detected", "One or more pods restarted.", "WARNING", 4.0),
        ("crashloop", "CrashLoopBackOff observed", "A pod entered CrashLoopBackOff.", "CRITICAL", 5.0),
    ],
    "PROMETHEUS": [
        ("latency_spike", "Latency spike (p99)", "p99 request latency rose sharply.", "WARNING", 5.0),
        ("error_spike", "Error rate spike (5xx)", "5xx error rate exceeded the alert threshold.", "CRITICAL", 6.0),
    ],
    "GRAFANA": [
        ("dashboard_alert", "Dashboard alert fired", "A Grafana dashboard alert fired.", "WARNING", 6.0),
        ("annotation", "Dashboard annotation added", "An annotation was added to the dashboard.", "INFO", 2.5),
    ],
    "DATADOG": [
        ("monitor_alert", "Datadog monitor CRITICAL", "A Datadog monitor transitioned to CRITICAL.", "CRITICAL", 6.5),
        ("incident", "Datadog incident declared", "A Datadog incident was declared.", "CRITICAL", 7.0),
    ],
}


def severity_rank(severity: str | None) -> int:
    return _SEVERITY_RANK.get((severity or "INFO").upper(), 0)


def build_events(providers: list[str], base_time: datetime) -> list[dict]:
    """Reconstruct a normalized, chronological event series (read-only).

    Returns a list of event dicts sorted by ``event_timestamp`` ascending. Only
    the given providers (those the investigating agent can read) contribute.
    """
    events: list[dict] = []
    for provider in providers:
        for event_type, title, description, severity, offset in _PROVIDER_EVENTS.get(provider, []):
            events.append(
                {
                    "provider": provider,
                    "event_type": event_type,
                    "event_timestamp": base_time + timedelta(minutes=offset),
                    "title": title,
                    "description": description,
                    "severity": severity,
                    "event_metadata": {"offset_min": offset, "source": "reconstructed"},
                }
            )
    events.sort(key=lambda e: e["event_timestamp"])
    return events


def _first(events, types) -> dict | None:
    for e in events:
        if _event_type(e) in types:
            return e
    return None


def _event_type(e) -> str:
    return e.get("event_type") if isinstance(e, dict) else getattr(e, "event_type", "")


def _event_ts(e):
    return e.get("event_timestamp") if isinstance(e, dict) else getattr(e, "event_timestamp", None)


def _event_provider(e) -> str:
    return e.get("provider") if isinstance(e, dict) else getattr(e, "provider", "")


def _event_title(e) -> str:
    return e.get("title") if isinstance(e, dict) else getattr(e, "title", "")


def _minutes_between(a, b) -> int | None:
    if a is None or b is None:
        return None
    return int(round((b - a).total_seconds() / 60.0))


def correlate(events: list) -> dict:
    """Correlate the timeline and score root-cause confidence.

    Accepts either event dicts (from ``build_events``) or persisted ORM rows.
    Returns a customer-safe trigger-analysis dict (no secrets).
    """
    ordered = sorted(events, key=lambda e: (_event_ts(e) or datetime.min))
    first_change = _first(ordered, CHANGE_TYPES)
    first_failure = _first(ordered, FAILURE_TYPES)
    first_alert = _first(ordered, ALERT_TYPES)
    first_degradation = _first(ordered, DEGRADATION_TYPES)

    change_to_failure = _minutes_between(_event_ts(first_change), _event_ts(first_failure))
    failure_to_alert = _minutes_between(_event_ts(first_failure), _event_ts(first_alert))

    impacted = sorted(
        {
            _event_provider(e)
            for e in ordered
            if _event_type(e) in (FAILURE_TYPES | ALERT_TYPES | DEGRADATION_TYPES)
        }
    )

    suspected_trigger = None
    suspected_provider = None
    confidence = 10
    reason = "No change event was found to correlate with the incident."

    if first_change is not None and first_failure is not None and (
        _event_ts(first_failure) >= _event_ts(first_change)
    ):
        gap = change_to_failure or 0
        score = 90 - min(gap, 30) * 1.5
        if first_alert is not None and _event_ts(first_alert) >= _event_ts(first_failure):
            score += 7
        confidence = int(max(5, min(99, round(score))))
        suspected_trigger = _event_title(first_change)
        suspected_provider = _event_provider(first_change)
        reason = (
            f"Failures began {gap} minute(s) after the "
            f"{_event_type(first_change).replace('_', ' ')} on {suspected_provider}."
        )
    elif first_change is not None:
        suspected_trigger = _event_title(first_change)
        suspected_provider = _event_provider(first_change)
        confidence = 30
        reason = "A change was detected but no clear failure correlation was found."

    return {
        "confidence_score": confidence,
        "suspected_trigger": suspected_trigger,
        "suspected_provider": suspected_provider,
        "reason": reason,
        "first_change_at": _event_ts(first_change),
        "first_failure_at": _event_ts(first_failure),
        "first_alert_at": _event_ts(first_alert),
        "first_degradation_at": _event_ts(first_degradation),
        "minutes_between_change_and_failure": change_to_failure,
        "minutes_between_failure_and_alert": failure_to_alert,
        "impacted_systems": impacted,
    }
