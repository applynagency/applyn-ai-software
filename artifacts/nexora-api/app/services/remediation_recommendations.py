"""Sprint 41A — Remediation Recommendation Engine.

Recommendation-only. Given an incident's RCA, timeline (40B), change
intelligence (40C), and tool evidence, this produces a *ranked* list of safe,
actionable remediation recommendations and answers the customer's question:
"What should I do next?".

The platform NEVER executes, deploys, rolls back, scales, or mutates anything —
this module emits advisory suggestions only. It is pure, deterministic, and
side-effect-free, so it works fully offline and is easy to test. Customer-safe
text only; no secrets are read, logged, or stored.
"""

from __future__ import annotations

# Recommendation categories.
DEPLOYMENT = "Deployment"
KUBERNETES = "Kubernetes"
INFRASTRUCTURE = "Infrastructure"
APPLICATION = "Application"
MONITORING = "Monitoring"

# Recovery-time buckets (minutes).
_RECOVERY_BUCKETS = (5, 15, 30, 60)

_RISK_WEIGHT = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


def _event_type(e) -> str:
    return (e.get("event_type") if isinstance(e, dict) else getattr(e, "event_type", "")) or ""


def _clamp(score: int) -> int:
    return int(max(5, min(99, round(score))))


def _bucket(minutes: int) -> int:
    """Snap an estimate to the nearest supported recovery bucket."""
    return min(_RECOVERY_BUCKETS, key=lambda b: abs(b - minutes))


def generate(
    *,
    timeline_events: list,
    change_analysis: dict | None,
    timeline_confidence: int | None,
) -> list[dict]:
    """Generate ranked remediation recommendations (recommendation-only).

    Inputs:
      * ``timeline_events``    — persisted 40B timeline events (signals).
      * ``change_analysis``    — 40C correlate_changes() output (suspected change).
      * ``timeline_confidence``— 40B correlation confidence (RCA/timeline).

    Returns a list of recommendation dicts sorted by priority and stamped with
    ``recommendation_order`` (1-based).
    """
    signals = {_event_type(e) for e in (timeline_events or [])}
    change = (change_analysis or {}).get("suspected_change")
    change_conf = int((change_analysis or {}).get("confidence_score") or 0)
    tl_conf = int(timeline_confidence or 0)
    # Blended base confidence (RCA/timeline + change intelligence).
    base = round(0.5 * tl_conf + 0.5 * change_conf) if (tl_conf or change_conf) else 30

    recs: list[dict] = []

    def add(rec_type, title, description, risk, confidence, recovery, reason, tags):
        recs.append(
            {
                "recommendation_type": rec_type,
                "title": title,
                "description": description,
                "risk_level": risk,
                "confidence_score": _clamp(confidence),
                "estimated_recovery_minutes": _bucket(recovery),
                "event_metadata": {"reason": reason, "signals": sorted(tags)},
            }
        )

    # --- Deployment followed by failure -> rollback / revert / compare -------
    if change and change.get("change_type") in ("deployment", "release"):
        version = change.get("version")
        provider = change.get("provider")
        vlabel = f" {version}" if version else ""
        add(
            DEPLOYMENT,
            f"Rollback deployment{vlabel}",
            (
                f"Roll back the suspected deployment{vlabel} on {provider} to the "
                "previously healthy version. Highest-impact action — validate before acting."
            ),
            "HIGH",
            min(99, change_conf + 3),
            15,
            change.get("reason") or "A deployment shortly preceded the failure.",
            {"deployment", "change_correlation"},
        )
        add(
            DEPLOYMENT,
            "Redeploy the previous known-good version",
            "If a rollback is not available, redeploy the last version that was healthy.",
            "HIGH",
            round(change_conf * 0.95),
            15,
            "Reverting the change is the fastest path to recovery.",
            {"deployment"},
        )
        add(
            APPLICATION,
            f"Compare changed files and review release notes{vlabel}",
            "Review the diff, PR, and release notes for the suspected change to confirm the regression.",
            "LOW",
            round(change_conf * 0.92),
            5,
            "Confirms the suspected change before any rollback.",
            {"change_correlation"},
        )

    # --- CrashLoopBackOff ----------------------------------------------------
    if "crashloop" in signals:
        add(
            KUBERNETES,
            "Inspect container startup logs",
            "Inspect the crashing container's startup logs to find the failure reason.",
            "LOW",
            round(base * 0.9),
            5,
            "CrashLoopBackOff observed in the timeline.",
            {"crashloop"},
        )
        add(
            KUBERNETES,
            "Review CrashLoopBackOff containers",
            "Check the container's command, readiness/liveness probes, and recent image change.",
            "MEDIUM",
            round(base * 0.88),
            5,
            "Recurring restarts indicate a startup or config fault.",
            {"crashloop"},
        )
        add(
            APPLICATION,
            "Validate environment variables and configuration",
            "Confirm required environment variables and configuration references are present and valid.",
            "LOW",
            round(base * 0.9),
            5,
            "Missing/invalid config is a common CrashLoopBackOff cause.",
            {"crashloop"},
        )

    # --- Pod restarts (without crashloop) ------------------------------------
    if "pod_restart" in signals and "crashloop" not in signals:
        add(
            KUBERNETES,
            "Restart affected pods",
            "Restart the impacted pods to clear a transient fault while you investigate.",
            "MEDIUM",
            round(base * 0.85),
            5,
            "Pod restarts were detected in the timeline.",
            {"pod_restart"},
        )

    # --- Memory spike --------------------------------------------------------
    if "memory_spike" in signals:
        add(
            INFRASTRUCTURE,
            "Increase memory limits / allocation",
            "Raise the memory request/limit for the affected workload to relieve pressure.",
            "MEDIUM",
            round(base * 0.85),
            30,
            "A memory spike was detected.",
            {"memory_spike"},
        )
        add(
            APPLICATION,
            "Investigate potential memory leak",
            "Profile heap usage and review recent changes for unbounded growth.",
            "LOW",
            round(base * 0.78),
            60,
            "Sustained memory growth suggests a leak.",
            {"memory_spike"},
        )

    # --- CPU spike -----------------------------------------------------------
    if "cpu_spike" in signals:
        add(
            KUBERNETES,
            "Scale replicas (increase) to absorb load",
            "Temporarily increase replica count to absorb elevated CPU load.",
            "MEDIUM",
            round(base * 0.82),
            15,
            "A CPU spike was detected.",
            {"cpu_spike"},
        )
        add(
            APPLICATION,
            "Review expensive / hot-path requests",
            "Identify the most expensive endpoints or queries driving CPU usage.",
            "LOW",
            round(base * 0.75),
            30,
            "Elevated CPU often traces to a hot code path.",
            {"cpu_spike"},
        )

    # --- Error spike ---------------------------------------------------------
    if "error_spike" in signals:
        add(
            APPLICATION,
            "Review application error logs",
            "Inspect recent application logs for the error signature driving the 5xx spike.",
            "LOW",
            round(base * 0.85),
            5,
            "An error-rate spike was detected.",
            {"error_spike"},
        )
        if not change:
            add(
                DEPLOYMENT,
                "Review recent deployments",
                "Check recent deployments/releases that may have introduced the errors.",
                "LOW",
                round(base * 0.8),
                5,
                "Error spikes frequently follow a release.",
                {"error_spike"},
            )

    # --- Latency / degradation -> monitoring ---------------------------------
    if "latency_spike" in signals:
        add(
            MONITORING,
            "Add latency monitoring and SLO tracking",
            "Add p95/p99 latency monitors and an SLO so regressions alert earlier next time.",
            "LOW",
            round(base * 0.72),
            15,
            "A latency spike was detected.",
            {"latency_spike"},
        )

    # --- Fallback: nothing actionable found ----------------------------------
    if not recs:
        add(
            MONITORING,
            "Add alert coverage and observability",
            "Connect read-only tools (metrics, logs, deploys) and add alert coverage, then re-run the investigation.",
            "LOW",
            base,
            15,
            "No actionable signals were correlated from the available evidence.",
            {"observability"},
        )

    # --- Rank: confidence desc, then risk desc, then faster recovery first ---
    recs.sort(
        key=lambda r: (
            r["confidence_score"],
            _RISK_WEIGHT.get(r["risk_level"], 0),
            -r["estimated_recovery_minutes"],
        ),
        reverse=True,
    )
    for i, r in enumerate(recs, start=1):
        r["recommendation_order"] = i
    return recs
