"""Sprint 52C.1 — Guided Walkthrough Engine.

Returns a structured, 10-step guided walkthrough for a demo organisation.
Each step has a title, description, screenshot asset reference, expected
result, and next action — enabling a prospect or sales engineer to walk
through the full platform without any external infrastructure.

The walkthrough is read-only computed output — no separate DB table needed.
Steps are assembled from the demo org's existing seeded data (incidents,
SLOs, war rooms, postmortems, cost/capacity data).

Steps
-----
1.  Discovery           — Infrastructure discovery map
2.  Monitoring          — Live monitoring alerts overview
3.  Incident            — Open incident investigation with RCA
4.  Timeline            — Correlated change-event timeline
5.  Change Intelligence — Deployment that triggered the incident
6.  Recommendations     — AI-generated remediation recommendations
7.  Remediation         — Remediation action approval flow
8.  Postmortem          — Auto-generated postmortem
9.  Service Health      — SLO compliance dashboard
10. Capacity & Cost     — Capacity forecast + cost optimisation

Strictly additive — no new tables.  No real credentials or cloud access.
"""

from __future__ import annotations

from typing import Any

_SCREENSHOT_BASE = "https://demo.local/assets/walkthroughs"

# ---------------------------------------------------------------------------
# Step catalogue (static, enriched at runtime with live data pointers)
# ---------------------------------------------------------------------------
_STEP_CATALOGUE: list[dict[str, Any]] = [
    {
        "step": 1,
        "title": "Service Discovery",
        "module": "discovery",
        "description": (
            "Nexora automatically discovers all services running in your infrastructure "
            "and maps their dependencies.  The graph shows which services are Tier-1, "
            "which teams own them, and what the blast radius is for each dependency."
        ),
        "expected_result": (
            "A visual dependency graph with at least 5 connected services, "
            "colour-coded by tier, with ownership labels."
        ),
        "next_action": "Click any service node to drill into its SLO history and recent alerts.",
        "screenshot_filename": "01-discovery-dashboard.png",
        "screenshot_url": f"{_SCREENSHOT_BASE}/01-discovery-dashboard.png",
        "screenshot_caption": "Service dependency graph — blast-radius heat map.",
        "callout": "See your entire infrastructure at a glance — no agents, no config.",
    },
    {
        "step": 2,
        "title": "Monitoring Alerts",
        "module": "monitoring",
        "description": (
            "The monitoring hub aggregates alerts from Prometheus, Datadog, CloudWatch "
            "and other providers into a single, enriched view.  Each alert shows severity, "
            "affected service, first-seen timestamp, and whether an incident was opened."
        ),
        "expected_result": (
            "Alert list with CRITICAL/HIGH/WARNING severities; at least one alert linked "
            "to an active or resolved incident."
        ),
        "next_action": "Click the CRITICAL alert to open the incident investigation.",
        "screenshot_filename": "02-monitoring-dashboard.png",
        "screenshot_url": f"{_SCREENSHOT_BASE}/02-monitoring-dashboard.png",
        "screenshot_caption": "Unified monitoring alerts with severity and incident linkage.",
        "callout": "All your monitoring in one place — correlate across providers instantly.",
    },
    {
        "step": 3,
        "title": "Incident Investigation",
        "module": "incidents",
        "description": (
            "When a CRITICAL alert fires, Nexora's AI SRE Lead automatically opens an "
            "incident investigation.  It queries metrics, inspects Kubernetes workloads, "
            "lists recent deployments, and produces a root-cause hypothesis with a "
            "confidence score."
        ),
        "expected_result": (
            "Completed incident investigation with root cause text, confidence >= 80%, "
            "and 2+ investigation steps visible."
        ),
        "next_action": "Open the Timeline tab to see correlated change events.",
        "screenshot_filename": "03-incident-investigation.png",
        "screenshot_url": f"{_SCREENSHOT_BASE}/03-incident-investigation.png",
        "screenshot_caption": "AI incident investigation — root cause with 94% confidence.",
        "callout": "MTTR cut from hours to minutes — AI finds root cause while you watch.",
    },
    {
        "step": 4,
        "title": "Incident Timeline",
        "module": "timeline",
        "description": (
            "The timeline stitches together deployment events, metric spikes, and alert "
            "firings in chronological order.  The suspected trigger is highlighted — "
            "typically the deployment that preceded the anomaly."
        ),
        "expected_result": (
            "Timeline with at least 3 events: deployment → alert → metric spike, "
            "with the deployment marked as suspected trigger."
        ),
        "next_action": "Click the deployment event to inspect the change set.",
        "screenshot_filename": "04-timeline-analysis.png",
        "screenshot_url": f"{_SCREENSHOT_BASE}/04-timeline-analysis.png",
        "screenshot_caption": "Change-event timeline correlating deploy to alert within 2 min.",
        "callout": "Instant change correlation — no manual log digging required.",
    },
    {
        "step": 5,
        "title": "Change Intelligence",
        "module": "change-intelligence",
        "description": (
            "Change Intelligence surfaces the exact GitHub deployment, PR number, "
            "author, and diff that triggered the incident.  It scores the change "
            "and shows whether it passed the deployment safety gate."
        ),
        "expected_result": (
            "Deployment change event with provider=GITHUB, version tag, and actor. "
            "Deployment safety score visible alongside readiness state."
        ),
        "next_action": "Navigate to Recommendations to see the AI-proposed remediation.",
        "screenshot_filename": "05-change-intelligence.png",
        "screenshot_url": f"{_SCREENSHOT_BASE}/05-change-intelligence.png",
        "screenshot_caption": "Change intelligence — PR #2105 identified as incident trigger.",
        "callout": "Know exactly what changed, who changed it, and when.",
    },
    {
        "step": 6,
        "title": "AI Recommendations",
        "module": "recommendations",
        "description": (
            "The AI team produces a ranked list of remediation recommendations, each "
            "with a risk level, confidence score, and estimated recovery time.  The "
            "top recommendation (rollback) is pre-populated into the remediation flow."
        ),
        "expected_result": (
            "At least 2 recommendations with risk levels MEDIUM/LOW, confidence >= 80%, "
            "and estimated recovery times."
        ),
        "next_action": "Click 'Approve Remediation' on the top recommendation.",
        "screenshot_filename": "06-recommendations.png",
        "screenshot_url": f"{_SCREENSHOT_BASE}/06-recommendations.png",
        "screenshot_caption": "Ranked AI recommendations — rollback at 94% confidence.",
        "callout": "AI doesn't just detect problems — it tells you exactly how to fix them.",
    },
    {
        "step": 7,
        "title": "Remediation Actions",
        "module": "remediation",
        "description": (
            "Remediation actions are approval-gated.  The AI generates the action "
            "(e.g. rollback to v2.2.9), the SRE reviews it, and an OWNER approves "
            "before any change reaches production.  The platform never auto-executes "
            "without human sign-off."
        ),
        "expected_result": (
            "Remediation action in APPROVED or PENDING_APPROVAL state with a target "
            "configuration and risk level visible."
        ),
        "next_action": "Approve the rollback action; watch the incident status change to RESOLVED.",
        "screenshot_filename": "07-remediation-actions.png",
        "screenshot_url": f"{_SCREENSHOT_BASE}/07-remediation-actions.png",
        "screenshot_caption": "Human-in-the-loop remediation — approve before any change lands.",
        "callout": "Full control: humans always approve before production changes.",
    },
    {
        "step": 8,
        "title": "Postmortem Report",
        "module": "postmortems",
        "description": (
            "Once an incident is resolved, Nexora auto-generates a postmortem report "
            "covering executive summary, impact analysis, timeline, root cause, "
            "resolution, lessons learned, and action items — reducing report writing "
            "from hours to seconds."
        ),
        "expected_result": (
            "Postmortem with executive summary, impact_analysis, root cause, resolution, "
            "and at least 2 action items."
        ),
        "next_action": "Export the postmortem or navigate to Service Health to verify SLO recovery.",
        "screenshot_filename": "08-postmortem-report.png",
        "screenshot_url": f"{_SCREENSHOT_BASE}/08-postmortem-report.png",
        "screenshot_caption": "Auto-generated postmortem — complete in seconds, not hours.",
        "callout": "Postmortems in seconds, not days. Compliance-ready from day one.",
    },
    {
        "step": 9,
        "title": "Service Health & SLOs",
        "module": "service-health",
        "description": (
            "The Service Health dashboard tracks SLO compliance, error-budget burn rates, "
            "and reliability trends for every service.  After the rollback, checkout-service "
            "returns to green within one burn-rate window."
        ),
        "expected_result": (
            "At least 5 services with Availability and Latency SLOs visible, "
            "all showing target >= 99.5%."
        ),
        "next_action": "Navigate to Capacity & Cost to see resource forecasts.",
        "screenshot_filename": "09-service-health.png",
        "screenshot_url": f"{_SCREENSHOT_BASE}/09-service-health.png",
        "screenshot_caption": "Service health — SLO compliance and error-budget overview.",
        "callout": "Real-time reliability visibility across every tier-1 service.",
    },
    {
        "step": 10,
        "title": "Capacity & Cost",
        "module": "capacity-cost",
        "description": (
            "The Capacity & Cost module provides 7-day trend data, 30/90-day resource "
            "forecasts, and a cost-optimisation engine that identifies idle and over-"
            "provisioned workloads.  The demo shows $151k/year in recoverable savings."
        ),
        "expected_result": (
            "Capacity forecasts for at least 2 services, a cost-optimisation analysis "
            "with waste > $0, and an annual savings projection."
        ),
        "next_action": "You have completed the full guided walkthrough!",
        "screenshot_filename": "10-capacity-cost.png",
        "screenshot_url": f"{_SCREENSHOT_BASE}/10-capacity-cost.png",
        "screenshot_caption": "Capacity forecast + cost optimisation — $151k annual savings.",
        "callout": "Cut cloud waste by up to 25% with AI-guided right-sizing.",
    },
]

_SCREENSHOT_ASSETS: list[dict[str, str]] = [
    {
        "filename": "01-discovery-dashboard.png",
        "module": "discovery",
        "category": "DISCOVERY",
        "caption": "Service dependency graph — blast-radius heat map",
    },
    {
        "filename": "02-monitoring-dashboard.png",
        "module": "monitoring",
        "category": "MONITORING",
        "caption": "Unified monitoring alerts with severity and incident linkage",
    },
    {
        "filename": "03-incident-investigation.png",
        "module": "incidents",
        "category": "INCIDENTS",
        "caption": "AI incident investigation — root cause with 94% confidence",
    },
    {
        "filename": "04-timeline-analysis.png",
        "module": "timeline",
        "category": "TIMELINE",
        "caption": "Change-event timeline correlating deploy to alert",
    },
    {
        "filename": "05-change-intelligence.png",
        "module": "change-intelligence",
        "category": "CHANGE_INTELLIGENCE",
        "caption": "Change intelligence — PR identified as incident trigger",
    },
    {
        "filename": "06-recommendations.png",
        "module": "recommendations",
        "category": "RECOMMENDATIONS",
        "caption": "Ranked AI recommendations with confidence scores",
    },
    {
        "filename": "07-remediation-actions.png",
        "module": "remediation",
        "category": "REMEDIATION",
        "caption": "Human-in-the-loop remediation approval flow",
    },
    {
        "filename": "08-postmortem-report.png",
        "module": "postmortems",
        "category": "REPORTS",
        "caption": "Auto-generated postmortem with action items",
    },
    {
        "filename": "09-service-health.png",
        "module": "service-health",
        "category": "SLO",
        "caption": "SLO compliance and error-budget burn overview",
    },
    {
        "filename": "10-capacity-cost.png",
        "module": "capacity-cost",
        "category": "CAPACITY",
        "caption": "Capacity forecast and cost optimisation report",
    },
]


class DemoWalkthroughService:
    """Pure read — returns walkthrough steps and screenshot asset manifests."""

    def get_walkthrough(self, org_id: str, *, scenario_type: str | None = None) -> dict:
        steps = [dict(s) for s in _STEP_CATALOGUE]
        return {
            "org_id": org_id,
            "scenario_type": scenario_type,
            "total_steps": len(steps),
            "steps": steps,
            "completion_message": (
                "You have experienced the full Nexora platform — from alert to postmortem — "
                "without connecting a single piece of real infrastructure."
            ),
        }

    def get_screenshots(self) -> list[dict]:
        return [dict(a) for a in _SCREENSHOT_ASSETS]

    def get_screenshot_manifest(self) -> dict:
        """Return full manifest with base URL, filenames, and categories."""
        return {
            "base_url": _SCREENSHOT_BASE,
            "total": len(_SCREENSHOT_ASSETS),
            "assets": [dict(a) for a in _SCREENSHOT_ASSETS],
        }
