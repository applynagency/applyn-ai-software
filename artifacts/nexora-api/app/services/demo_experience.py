"""Sprint 56E.5 — Demo Experience Platform.

Lets a sales engineer run a complete, polished demonstration with zero manual
preparation. It turns the deterministic documentation catalog into audience-ready
demo scenarios:

* Executive Demo
* Technical Demo
* CTO Demo
* Startup Demo

Each scenario is a full demo script — ordered scenes that each carry narration,
the on-screen action, talking points, presenter notes, and the expected outcome.
The engine also exposes a demo dashboard, a scenario launcher, a streamlined
Sales Mode view, and Launch / Reset / Replay lifecycle actions (computed
statelessly, no DB).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import NotFoundError
from app.services.customer_success_content import get_module
from app.services.screenshot_assets import AREAS

_AREA_SLUG_BY_ROUTE = {a["route"]: a["slug"] for a in AREAS}
_VALID_ACTIONS = {"launch", "reset", "replay", "advance"}

# Audience-tailored demo scenarios. Each scene = (module_key, minutes, focus).
SCENARIOS: list[dict[str, Any]] = [
    {
        "key": "executive-demo",
        "audience": "Executive",
        "title": "Executive Demo",
        "persona": "VP Engineering / CIO",
        "icon": "briefcase",
        "duration_minutes": 15,
        "summary": "A business-outcome story: reliability, faster incident response, and "
                   "cloud savings, summarised in a leadership-ready report.",
        "objectives": [
            "Show reliability and business impact at a glance.",
            "Demonstrate faster incident response and lower MTTR.",
            "Quantify cost savings and ROI.",
            "Leave with an exportable executive report.",
        ],
        "scenes": [
            ("executive-reports", 4, "Open with the one-screen executive view of reliability and ROI."),
            ("service-health", 3, "Drill into service health to show reliability is measured, not guessed."),
            ("incidents", 4, "Show how an incident is investigated and resolved fast."),
            ("cost", 4, "Close on cloud savings and quantified ROI."),
        ],
    },
    {
        "key": "technical-demo",
        "audience": "Technical",
        "title": "Technical Demo",
        "persona": "SRE / DevOps Engineer",
        "icon": "cpu",
        "duration_minutes": 30,
        "summary": "A hands-on deep dive: discovery, monitoring, full incident "
                   "investigation, timeline, remediation, and postmortems.",
        "objectives": [
            "Prove automatic infrastructure discovery and monitoring.",
            "Walk a full incident from alert to root cause.",
            "Show the timeline and change intelligence.",
            "Apply a safe remediation and generate a postmortem.",
        ],
        "scenes": [
            ("discovery", 4, "Show infrastructure discovered automatically — no manual inventory."),
            ("monitoring", 5, "Demonstrate live monitoring signals and thresholds."),
            ("incidents", 6, "Open a real incident and investigate it with AI assistance."),
            ("timeline", 5, "Use the timeline and change intelligence to pin the root cause."),
            ("remediation", 5, "Apply a safe, recommended remediation action."),
            ("postmortems", 5, "Generate an exportable postmortem in one click."),
        ],
    },
    {
        "key": "cto-demo",
        "audience": "CTO",
        "title": "CTO Demo",
        "persona": "CTO / VP of Engineering",
        "icon": "target",
        "duration_minutes": 20,
        "summary": "A strategic view: SLO posture, change-failure risk, capacity and "
                   "cost strategy, all rolled into executive reporting.",
        "objectives": [
            "Show reliability strategy via SLOs and error budgets.",
            "Quantify change-failure risk before it ships.",
            "Connect capacity and cost to investment decisions.",
            "Tie it together with executive reporting.",
        ],
        "scenes": [
            ("executive-reports", 4, "Frame the strategic picture with the executive report."),
            ("slos", 4, "Show SLO posture and error-budget risk across services."),
            ("change-failure", 4, "Demonstrate change-failure prediction reducing risky releases."),
            ("capacity", 4, "Show capacity planning informing investment."),
            ("cost", 4, "Close on cost strategy and spend trends."),
        ],
    },
    {
        "key": "startup-demo",
        "audience": "Startup",
        "title": "Startup Demo",
        "persona": "Founder / Early Engineer",
        "icon": "rocket",
        "duration_minutes": 10,
        "summary": "A fast, lean path to value: connect, watch, respond, and save — "
                   "with almost no setup.",
        "objectives": [
            "Show value in minutes with near-zero setup.",
            "Connect and discover infrastructure instantly.",
            "Catch and resolve an incident fast.",
            "Spot an immediate cost saving.",
        ],
        "scenes": [
            ("discovery", 3, "Connect a cloud account and watch infrastructure appear."),
            ("monitoring", 3, "Turn on monitoring with sensible defaults."),
            ("incidents", 2, "Catch and triage an incident without a war room."),
            ("cost", 2, "Find an immediate saving to fund the tool itself."),
        ],
    },
]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _screenshot_url(route: str, shot: str = "overview") -> str:
    r = route or "/"
    return f"/nexora-api/v1/customer-success/screenshot-render?route={r}&shot={shot}&device=desktop"


def _screenshot_id(route: str, shot: str = "overview") -> str:
    slug = _AREA_SLUG_BY_ROUTE.get(route)
    return f"{slug}-{shot}-desktop" if slug else f"route-{(route or '/').strip('/').replace('/', '-') or 'home'}-{shot}-desktop"


class DemoExperienceEngine:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] | None = None

    # ------------------------------------------------------- scene builder
    def _scene(self, order: int, module_key: str, minutes: int, focus: str) -> dict[str, Any]:
        m = get_module(module_key)
        if not m:
            raise ValueError(f"Demo scenario references unknown module: {module_key}")
        overview = m.get("overview", {})
        md = m.get("metadata", {})
        steps = m.get("steps", [])
        first_step = steps[0] if steps else {}
        outcomes = md.get("expected_outcomes", []) or []
        talking_points = [
            f"What it is: {overview.get('what', m['name'])}",
            f"Why it matters: {overview.get('why', md.get('business_value', 'Improves reliability.'))}",
        ]
        if md.get("business_value"):
            talking_points.append(f"Business value: {md['business_value']}.")
        if outcomes:
            talking_points.append("Outcomes: " + ", ".join(outcomes) + ".")
        expected = outcomes[0] if outcomes else f"The audience sees {m['name']} in action."
        return {
            "order": order,
            "title": m["name"],
            "module": module_key,
            "route": m["route"],
            "duration_minutes": minutes,
            "focus": focus,
            "narration": f"{focus} {overview.get('what', '')}".strip(),
            "action": str(first_step.get("action", f"Open {m['name']}.")),
            "talking_points": talking_points,
            "presenter_notes": (
                f"Lead with the outcome, not the feature. Tie {m['name']} back to the "
                f"audience's priority: {md.get('business_value', 'reliability')}. "
                f"If asked, the underlying flow is: {first_step.get('expected', 'live data loads')}."
            ),
            "expected_outcome": expected,
            "screenshot_id": _screenshot_id(m["route"]),
            "screenshot_url": _screenshot_url(m["route"]),
        }

    def _build(self) -> dict[str, dict[str, Any]]:
        if self._cache is not None:
            return self._cache
        out: dict[str, dict[str, Any]] = {}
        for s in SCENARIOS:
            scenes = [
                self._scene(i, mk, mins, focus)
                for i, (mk, mins, focus) in enumerate(s["scenes"], start=1)
            ]
            talking_points = [tp for sc in scenes for tp in sc["talking_points"]]
            expected_outcomes = [sc["expected_outcome"] for sc in scenes]
            presenter_notes = (
                f"Audience: {s['persona']}. Keep it to ~{s['duration_minutes']} minutes. "
                f"Open with the headline outcome, run the {len(scenes)} scenes in order, "
                f"and close by restating the value for a {s['audience'].lower()} audience. "
                "Use Reset between runs to return to clean demo data; use Replay to start over."
            )
            out[s["key"]] = {
                "key": s["key"],
                "audience": s["audience"],
                "title": s["title"],
                "persona": s["persona"],
                "icon": s["icon"],
                "summary": s["summary"],
                "duration_minutes": s["duration_minutes"],
                "objectives": list(s["objectives"]),
                "scenes": scenes,
                "scene_count": len(scenes),
                "talking_points": talking_points,
                "presenter_notes": presenter_notes,
                "expected_outcomes": expected_outcomes,
                "modules": [sc["module"] for sc in scenes],
            }
        self._cache = out
        return out

    def _scene_ids(self, scenario: dict[str, Any]) -> list[str]:
        return [f"{scenario['key']}-scene-{sc['order']}" for sc in scenario["scenes"]]

    # ------------------------------------------------------- public API
    def scenarios(self) -> list[dict[str, Any]]:
        return list(self._build().values())

    def get_scenario(self, key: str) -> dict[str, Any]:
        s = self._build().get(key)
        if not s:
            raise NotFoundError("Demo scenario", key)
        return s

    def dashboard(self) -> dict[str, Any]:
        scenarios = self._build().values()
        summaries = [
            {k: s[k] for k in (
                "key", "audience", "title", "persona", "icon", "summary",
                "duration_minutes", "scene_count", "objectives",
            )}
            for s in scenarios
        ]
        total_scenes = sum(s["scene_count"] for s in scenarios)
        return {
            "scenarios": summaries,
            "totals": {
                "scenarios": len(summaries),
                "audiences": sorted({s["audience"] for s in scenarios}),
                "total_scenes": total_scenes,
                "shortest_minutes": min((s["duration_minutes"] for s in scenarios), default=0),
                "longest_minutes": max((s["duration_minutes"] for s in scenarios), default=0),
            },
        }

    def sales_mode(self, key: str) -> dict[str, Any]:
        """A streamlined presenter view: just script, notes, talking points, outcomes."""
        s = self.get_scenario(key)
        return {
            "key": s["key"],
            "audience": s["audience"],
            "title": s["title"],
            "persona": s["persona"],
            "duration_minutes": s["duration_minutes"],
            "presenter_notes": s["presenter_notes"],
            "objectives": s["objectives"],
            "expected_outcomes": s["expected_outcomes"],
            "script": [
                {
                    "order": sc["order"],
                    "title": sc["title"],
                    "route": sc["route"],
                    "duration_minutes": sc["duration_minutes"],
                    "say": sc["narration"],
                    "do": sc["action"],
                    "talking_points": sc["talking_points"],
                    "presenter_notes": sc["presenter_notes"],
                    "expected_outcome": sc["expected_outcome"],
                    "screenshot_url": sc["screenshot_url"],
                }
                for sc in s["scenes"]
            ],
        }

    def launch(self, key: str) -> dict[str, Any]:
        """Scenario launcher — start a fresh demo run."""
        return self.state(key, action="launch")

    def state(
        self, key: str, *, action: str = "advance",
        completed: list[str] | None = None, started_at: str | None = None,
    ) -> dict[str, Any]:
        scenario = self.get_scenario(key)
        action = (action or "advance").lower()
        if action not in _VALID_ACTIONS:
            action = "advance"
        all_ids = self._scene_ids(scenario)
        total = len(all_ids)
        completed = [c for c in (completed or []) if c in all_ids]

        if action in ("launch", "replay"):
            completed = []
            started_at = _now()
        elif action == "reset":
            completed = []
            started_at = None
        elif started_at is None:
            started_at = _now()

        percent = round(len(completed) / total * 100) if total else 0
        current_index = next((i for i, sid in enumerate(all_ids) if sid not in completed), total)
        completed_at: str | None = None

        if action == "reset":
            status = "reset"
            percent = 0
            current_index = 0
        elif len(completed) >= total and total > 0:
            status = "completed"
            percent = 100
            current_index = total
            completed_at = _now()
        elif action in ("launch", "replay"):
            status = "running"
        else:
            status = "running"

        current_scene = scenario["scenes"][current_index] if current_index < total else None
        return {
            "key": scenario["key"],
            "title": scenario["title"],
            "audience": scenario["audience"],
            "action": action,
            "status": status,
            "total_scenes": total,
            "completed_scenes": len(completed),
            "completed_scene_ids": completed,
            "completion_percentage": percent,
            "current_scene_index": current_index,
            "current_scene": current_scene,
            "started_at": started_at,
            "completed_at": completed_at,
        }
