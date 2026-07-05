"""Sprint 56E.4 — Time To Value Optimization.

Guided "first success" experiences that get a new customer to real platform value
within 15 minutes. Six milestones, each a short, prerequisite-checked quickstart:

* First Incident
* First Service
* First SLO
* First Deployment Review
* First Cost Optimization
* First Executive Report

Each experience carries a goal, prerequisites, ordered steps (with time
estimates), an expected outcome, and measurable success criteria. The engine
also produces a success checklist, stateless progress tracking, and a completion
status, plus a time-to-value dashboard. Deterministic, read-only, no DB.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import NotFoundError
from app.services.customer_success_content import get_module

# The promise: every guided experience must fit inside this budget.
TIME_TO_VALUE_BUDGET_MINUTES = 15


def _step(order: int, action: str, detail: str, expected: str, minutes: int) -> dict[str, Any]:
    return {
        "order": order,
        "action": action,
        "detail": detail,
        "expected_result": expected,
        "estimated_minutes": minutes,
    }


def _crit(cid: str, label: str) -> dict[str, str]:
    return {"id": cid, "label": label}


# Authored experiences. `module` maps to customer_success_content.MODULES for the route.
EXPERIENCES: list[dict[str, Any]] = [
    {
        "key": "first-incident",
        "title": "Resolve Your First Incident",
        "milestone": "First Incident",
        "module": "incidents",
        "icon": "alert-triangle",
        "goal": "Detect, investigate, and acknowledge your first incident so you know "
                "the likely cause and the next action.",
        "prerequisites": [
            "Infrastructure is connected",
            "Monitoring is active and has produced at least one signal",
        ],
        "steps": [
            _step(1, "Open Operations → Incidents.", "The incident list is your triage queue.",
                  "The active incidents list loads, sorted by severity.", 2),
            _step(2, "Open the highest-severity active incident.", "Start where impact is greatest.",
                  "The incident detail opens with timeline and correlated signals.", 3),
            _step(3, "Review the timeline and probable root cause.", "The timeline pins what changed and when.",
                  "You can see the correlated events and a probable root cause.", 3),
            _step(4, "Open the top recommendation.", "Recommendations are ranked by confidence.",
                  "A ranked recommendation shows confidence and estimated recovery.", 3),
            _step(5, "Acknowledge the incident and assign an owner.", "This closes the loop on triage.",
                  "The incident is acknowledged and has an owner.", 2),
        ],
        "expected_outcome": "You triaged your first incident and know the likely cause and the next action.",
        "success_criteria": [
            _crit("inc-opened", "Opened an incident's detail view"),
            _crit("inc-cause", "Reviewed the timeline and probable root cause"),
            _crit("inc-reco", "Viewed a ranked recommendation"),
            _crit("inc-ack", "Acknowledged or assigned the incident"),
        ],
    },
    {
        "key": "first-service",
        "title": "See Your First Service's Health",
        "milestone": "First Service",
        "module": "service-health",
        "icon": "heart-pulse",
        "goal": "View the health of your first service and understand what drives its score.",
        "prerequisites": [
            "Infrastructure discovery has run",
            "At least one service is being monitored",
        ],
        "steps": [
            _step(1, "Open Service Health.", "This lists every monitored service with a health score.",
                  "The service list loads with health scores.", 2),
            _step(2, "Select a service to open its detail.", "Pick a service you own.",
                  "The service detail opens with its health score.", 2),
            _step(3, "Review the health score and SLO status.", "The score summarises reliability.",
                  "You can see the health score and current SLO status.", 3),
            _step(4, "Review dependencies and active signals.", "Dependencies explain blast radius.",
                  "Dependencies and any active signals are shown.", 3),
            _step(5, "Star the service to track it.", "Starred services surface on your dashboard.",
                  "The service is starred and tracked.", 2),
        ],
        "expected_outcome": "You can see a service's health score and exactly what drives it.",
        "success_criteria": [
            _crit("svc-open", "Opened a service's detail view"),
            _crit("svc-score", "Reviewed the health score and SLO status"),
            _crit("svc-deps", "Reviewed dependencies and signals"),
            _crit("svc-track", "Starred the service to track it"),
        ],
    },
    {
        "key": "first-slo",
        "title": "Define Your First SLO",
        "milestone": "First SLO",
        "module": "slos",
        "icon": "target",
        "goal": "Define your first SLO and see its error budget.",
        "prerequisites": [
            "A service is being monitored",
            "You know the target availability (e.g. 99.9%)",
        ],
        "steps": [
            _step(1, "Open SLOs & Error Budgets.", "This is where reliability targets live.",
                  "The SLO list loads.", 2),
            _step(2, "Create an SLO from a template.", "Templates cover common availability and latency goals.",
                  "A new SLO draft opens.", 3),
            _step(3, "Set the target objective.", "For example, 99.9% availability over 30 days.",
                  "The target is set on the SLO.", 3),
            _step(4, "Review the resulting error budget.", "The budget is how much unreliability you can spend.",
                  "The error budget and burn rate are displayed.", 3),
            _step(5, "Save the SLO.", "Saving begins tracking against the target.",
                  "The SLO is saved and tracking.", 2),
        ],
        "expected_outcome": "You have a live SLO with a target and a visible error budget.",
        "success_criteria": [
            _crit("slo-open", "Opened SLOs & Error Budgets"),
            _crit("slo-target", "Set an SLO target objective"),
            _crit("slo-budget", "Reviewed the error budget"),
            _crit("slo-saved", "Saved the SLO"),
        ],
    },
    {
        "key": "first-deployment-review",
        "title": "Run Your First Deployment Review",
        "milestone": "First Deployment Review",
        "module": "deployment-safety",
        "icon": "shield-check",
        "goal": "Assess a deployment's risk and make a confident go/no-go decision.",
        "prerequisites": [
            "A change source (CI/CD or Git) is connected",
            "There is a recent or planned deployment to review",
        ],
        "steps": [
            _step(1, "Open Deployment Safety.", "This scores deployments by risk.",
                  "The deployment list loads with risk scores.", 2),
            _step(2, "Select a deployment or change to review.", "Pick a recent or upcoming change.",
                  "The deployment detail opens.", 3),
            _step(3, "Review the risk score and contributing signals.", "Signals explain why risk is high or low.",
                  "The risk score and signals are shown.", 3),
            _step(4, "Review the recommended safety gates.", "Gates are the checks to run before shipping.",
                  "Recommended gates are listed.", 3),
            _step(5, "Approve or hold the deployment.", "Record your decision.",
                  "The deployment is approved or held.", 2),
        ],
        "expected_outcome": "You assessed a deployment's risk and made a go/no-go decision.",
        "success_criteria": [
            _crit("dep-open", "Opened a deployment's review"),
            _crit("dep-risk", "Reviewed the risk score and signals"),
            _crit("dep-gates", "Reviewed recommended safety gates"),
            _crit("dep-decision", "Approved or held the deployment"),
        ],
    },
    {
        "key": "first-cost-optimization",
        "title": "Find Your First Cost Saving",
        "milestone": "First Cost Optimization",
        "module": "cost",
        "icon": "piggy-bank",
        "goal": "Find a concrete cost-saving opportunity with estimated impact.",
        "prerequisites": [
            "Cloud accounts are connected",
            "Billing or usage data is available",
        ],
        "steps": [
            _step(1, "Open Cost Optimization.", "This surfaces spend and savings opportunities.",
                  "The cost overview loads.", 2),
            _step(2, "Review the spend overview.", "Understand where the money goes.",
                  "Spend by service and trend are shown.", 3),
            _step(3, "Open the top savings recommendation.", "Recommendations are ranked by impact.",
                  "A recommendation opens with details.", 3),
            _step(4, "Review estimated savings and risk.", "Confirm the saving is worth it.",
                  "Estimated savings and risk are displayed.", 3),
            _step(5, "Mark the recommendation for action.", "Track it to completion.",
                  "The recommendation is marked for action.", 2),
        ],
        "expected_outcome": "You found a concrete saving with estimated impact you can act on.",
        "success_criteria": [
            _crit("cost-open", "Opened Cost Optimization"),
            _crit("cost-reco", "Opened a savings recommendation"),
            _crit("cost-savings", "Reviewed estimated savings and risk"),
            _crit("cost-action", "Marked a recommendation for action"),
        ],
    },
    {
        "key": "first-executive-report",
        "title": "Generate Your First Executive Report",
        "milestone": "First Executive Report",
        "module": "executive-reports",
        "icon": "file-bar-chart",
        "goal": "Produce an executive summary you can share with leadership.",
        "prerequisites": [
            "At least one day of platform data",
        ],
        "steps": [
            _step(1, "Open Executive Reports.", "This produces leadership-ready summaries.",
                  "The reports view loads.", 2),
            _step(2, "Select the reporting period.", "Choose the window to summarise.",
                  "The reporting period is set.", 2),
            _step(3, "Generate the report.", "The platform compiles reliability, incidents, and cost.",
                  "The report is generated.", 3),
            _step(4, "Review reliability, incidents, and cost summaries.", "This is the story for leadership.",
                  "The summary sections are populated.", 3),
            _step(5, "Export or share the report.", "Send it to stakeholders.",
                  "The report is exported or shared.", 2),
        ],
        "expected_outcome": "You produced an executive summary you can share with leadership.",
        "success_criteria": [
            _crit("exec-open", "Opened Executive Reports"),
            _crit("exec-generate", "Generated a report"),
            _crit("exec-review", "Reviewed reliability, incidents, and cost summaries"),
            _crit("exec-export", "Exported or shared the report"),
        ],
    },
]


class TimeToValueEngine:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] | None = None

    def _build(self) -> dict[str, dict[str, Any]]:
        if self._cache is not None:
            return self._cache
        out: dict[str, dict[str, Any]] = {}
        for e in EXPERIENCES:
            module = get_module(e["module"])
            if not module:
                raise ValueError(f"TTV experience references unknown module: {e['module']}")
            steps = [dict(s) for s in e["steps"]]
            estimated = sum(s["estimated_minutes"] for s in steps)
            out[e["key"]] = {
                "key": e["key"],
                "title": e["title"],
                "milestone": e["milestone"],
                "module": e["module"],
                "route": module["route"],
                "icon": e["icon"],
                "goal": e["goal"],
                "prerequisites": list(e["prerequisites"]),
                "steps": steps,
                "step_count": len(steps),
                "expected_outcome": e["expected_outcome"],
                "success_criteria": [dict(c) for c in e["success_criteria"]],
                "criteria_count": len(e["success_criteria"]),
                "estimated_minutes": estimated,
                "within_time_to_value": estimated <= TIME_TO_VALUE_BUDGET_MINUTES,
                "time_to_value_budget": TIME_TO_VALUE_BUDGET_MINUTES,
            }
        self._cache = out
        return out

    def _progress(self, exp: dict[str, Any], completed: set[str]) -> dict[str, Any]:
        checklist = [
            {**c, "completed": c["id"] in completed}
            for c in exp["success_criteria"]
        ]
        done = sum(1 for c in checklist if c["completed"])
        total = len(checklist)
        percent = round(done / total * 100) if total else 0
        if done == 0:
            status = "not_started"
        elif done >= total:
            status = "completed"
        else:
            status = "in_progress"
        next_item = next((c["id"] for c in checklist if not c["completed"]), None)
        return {
            **{k: exp[k] for k in (
                "key", "title", "milestone", "module", "route", "icon", "goal",
                "prerequisites", "steps", "step_count", "expected_outcome",
                "criteria_count", "estimated_minutes", "within_time_to_value",
                "time_to_value_budget",
            )},
            "success_checklist": checklist,
            "completed_criteria": done,
            "remaining_criteria": total - done,
            "completion_percent": percent,
            "status": status,
            "next_criterion": next_item,
            "value_reached": status == "completed",
        }

    # ------------------------------------------------------- public API
    def experiences(self, completed: set[str] | None = None) -> list[dict[str, Any]]:
        completed = completed or set()
        return [self._progress(e, completed) for e in self._build().values()]

    def get_experience(self, key: str, completed: set[str] | None = None) -> dict[str, Any]:
        exp = self._build().get(key)
        if not exp:
            raise NotFoundError("Time-to-value experience", key)
        return self._progress(exp, completed or set())

    def dashboard(self, completed: set[str] | None = None) -> dict[str, Any]:
        completed = completed or set()
        progressed = [self._progress(e, completed) for e in self._build().values()]
        total = len(progressed)
        reached = sum(1 for p in progressed if p["value_reached"])
        overall_percent = round(sum(p["completion_percent"] for p in progressed) / total) if total else 0
        fastest = min((p["estimated_minutes"] for p in progressed), default=0)
        slowest = max((p["estimated_minutes"] for p in progressed), default=0)
        return {
            "experiences": progressed,
            "totals": {
                "experiences": total,
                "time_to_value_budget": TIME_TO_VALUE_BUDGET_MINUTES,
                "fastest_minutes": fastest,
                "slowest_minutes": slowest,
                "all_within_budget": all(p["within_time_to_value"] for p in progressed),
            },
            "overall": {
                "completion_percent": overall_percent,
                "milestones_reached": reached,
                "milestones_total": total,
                "first_value_reached": reached >= 1,
                "fully_activated": reached == total and total > 0,
            },
        }
