"""Sprint 56E.3 — Customer Success Academy.

Structured, role-based learning tracks that let a customer onboard new employees
without assistance. Five tracks map the platform to real job roles:

* Platform Administrator
* DevOps Engineer
* SRE Engineer
* Engineering Manager
* CTO

Each track carries learning objectives, required modules (in order), an estimated
time, a difficulty, and computed progress. The academy exposes a dashboard,
stateless progress tracking, and completion badges. Deterministic, read-only,
no DB.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import NotFoundError
from app.services.customer_success_content import get_module

# Minutes to learn a module, by its difficulty.
_DIFF_MINUTES = {"Beginner": 20, "Intermediate": 35, "Advanced": 50}
_DIFF_RANK = {"Beginner": 1, "Intermediate": 2, "Advanced": 3}
_RANK_DIFF = {v: k for k, v in _DIFF_RANK.items()}
_TIER_FOR_DIFF = {"Beginner": "Bronze", "Intermediate": "Silver", "Advanced": "Gold"}

# Authored role tracks. Module keys reference customer_success_content.MODULES.
TRACKS: list[dict[str, Any]] = [
    {
        "key": "platform-administrator",
        "role": "Platform Administrator",
        "title": "Platform Administrator Track",
        "icon": "shield",
        "summary": "Stand up the platform: connect infrastructure, configure discovery and "
                   "monitoring, and automate operations with AI teams and workflows.",
        "objectives": [
            "Connect cloud accounts and clusters so the platform can see your estate.",
            "Run and schedule infrastructure discovery and validate coverage.",
            "Configure monitoring signals, thresholds, and alert routing.",
            "Set up AI teams to triage and act on operational signals.",
            "Build reusable workflows that automate routine operational tasks.",
        ],
        "module_keys": ["onboarding", "discovery", "monitoring", "ai-teams", "workflows"],
    },
    {
        "key": "devops-engineer",
        "role": "DevOps Engineer",
        "title": "DevOps Engineer Track",
        "icon": "wrench",
        "summary": "Operate the delivery lifecycle: discover infrastructure, watch it, "
                   "respond to incidents, remediate, and learn from postmortems.",
        "objectives": [
            "Discover and map the infrastructure you are responsible for.",
            "Monitor services and understand what healthy looks like.",
            "Detect, investigate, and triage incidents quickly.",
            "Apply safe remediation actions to restore service.",
            "Run blameless postmortems and close the loop on follow-ups.",
        ],
        "module_keys": ["discovery", "monitoring", "incidents", "remediation", "postmortems"],
    },
    {
        "key": "sre-engineer",
        "role": "SRE Engineer",
        "title": "SRE Engineer Track",
        "icon": "activity",
        "summary": "Master reliability operations: monitoring, incident intelligence, "
                   "timelines, recommendations, remediation, service health, and SLOs.",
        "objectives": [
            "Use monitoring to spot reliability regressions before customers do.",
            "Investigate incidents using intelligence, timelines, and recommendations.",
            "Drive remediation and verify recovery.",
            "Track service health and run services against SLOs and error budgets.",
            "Interpret reliability scores to prioritise reliability work.",
        ],
        "module_keys": ["monitoring", "incidents", "timeline", "recommendations",
                        "remediation", "service-health", "slos"],
    },
    {
        "key": "engineering-manager",
        "role": "Engineering Manager",
        "title": "Engineering Manager Track",
        "icon": "users",
        "summary": "Lead a reliable team: oversee incidents and postmortems, track service "
                   "health, plan capacity and cost, and report outcomes to stakeholders.",
        "objectives": [
            "Oversee incident response and ensure postmortems drive improvement.",
            "Monitor service health across the teams you support.",
            "Plan capacity to stay ahead of growth.",
            "Manage and optimise cloud cost.",
            "Communicate reliability outcomes with executive reports.",
        ],
        "module_keys": ["incidents", "postmortems", "service-health", "capacity",
                        "cost", "executive-reports"],
    },
    {
        "key": "cto",
        "role": "CTO",
        "title": "CTO Track",
        "icon": "briefcase",
        "summary": "See the whole picture: executive reporting, SLO posture, cost and "
                   "capacity strategy, and change-failure risk across the organisation.",
        "objectives": [
            "Read executive reports to understand reliability at a glance.",
            "Assess SLO posture and error-budget risk across services.",
            "Set cost strategy and understand spend trends.",
            "Use capacity planning to inform investment decisions.",
            "Understand change-failure risk and its business impact.",
        ],
        "module_keys": ["executive-reports", "slos", "cost", "capacity", "change-failure"],
    },
]

_GRADUATE_BADGE = {
    "key": "badge-academy-graduate",
    "name": "Academy Graduate",
    "description": "Awarded for completing every Customer Success Academy track.",
    "tier": "Platinum",
    "icon": "graduation-cap",
    "track": None,
    "criteria": "Earn all five track certification badges.",
}


def _module_minutes(m: dict[str, Any]) -> int:
    diff = m.get("metadata", {}).get("difficulty", "Intermediate")
    return _DIFF_MINUTES.get(diff, 35)


def _label_minutes(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    h, m = divmod(minutes, 60)
    return f"{h}h {m:02d}m" if m else f"{h}h"


class CustomerSuccessAcademy:
    def __init__(self) -> None:
        self._tracks: dict[str, dict[str, Any]] | None = None

    # ------------------------------------------------------- assembly
    def _track_modules(self, module_keys: list[str]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for order, key in enumerate(module_keys, start=1):
            m = get_module(key)
            if not m:
                raise ValueError(f"Academy references unknown module: {key}")
            diff = m["metadata"]["difficulty"]
            out.append({
                "order": order,
                "key": key,
                "name": m["name"],
                "route": m["route"],
                "difficulty": diff,
                "estimated_minutes": _module_minutes(m),
            })
        return out

    def _badge_for(self, track: dict[str, Any], modules: list[dict[str, Any]], difficulty: str) -> dict[str, Any]:
        return {
            "key": f"badge-{track['key']}",
            "name": f"{track['role']} Certified",
            "description": f"Awarded for completing all {len(modules)} modules of the {track['role']} track.",
            "tier": _TIER_FOR_DIFF.get(difficulty, "Silver"),
            "icon": track["icon"],
            "track": track["key"],
            "criteria": "Complete 100% of the track's required modules.",
        }

    def _build(self) -> dict[str, dict[str, Any]]:
        if self._tracks is not None:
            return self._tracks
        tracks: dict[str, dict[str, Any]] = {}
        for t in TRACKS:
            modules = self._track_modules(t["module_keys"])
            rank = max((_DIFF_RANK[m["difficulty"]] for m in modules), default=2)
            difficulty = _RANK_DIFF[rank]
            estimated = sum(m["estimated_minutes"] for m in modules)
            tracks[t["key"]] = {
                "key": t["key"],
                "role": t["role"],
                "title": t["title"],
                "icon": t["icon"],
                "summary": t["summary"],
                "objectives": list(t["objectives"]),
                "modules": modules,
                "module_count": len(modules),
                "difficulty": difficulty,
                "estimated_minutes": estimated,
                "estimated_label": _label_minutes(estimated),
                "badge": self._badge_for(t, modules, difficulty),
            }
        self._tracks = tracks
        return tracks

    # ------------------------------------------------------- progress
    def _progress(self, track: dict[str, Any], completed: set[str]) -> dict[str, Any]:
        modules = [
            {**m, "completed": m["key"] in completed}
            for m in track["modules"]
        ]
        done = sum(1 for m in modules if m["completed"])
        total = len(modules)
        percent = round(done / total * 100) if total else 0
        remaining_minutes = sum(m["estimated_minutes"] for m in modules if not m["completed"])
        if done == 0:
            status = "not_started"
        elif done >= total:
            status = "completed"
        else:
            status = "in_progress"
        # The next module to study is the first incomplete one.
        next_module = next((m["key"] for m in modules if not m["completed"]), None)
        return {
            "key": track["key"],
            "role": track["role"],
            "title": track["title"],
            "icon": track["icon"],
            "summary": track["summary"],
            "objectives": track["objectives"],
            "difficulty": track["difficulty"],
            "estimated_minutes": track["estimated_minutes"],
            "estimated_label": track["estimated_label"],
            "module_count": total,
            "modules": modules,
            "completed_modules": done,
            "remaining_modules": total - done,
            "remaining_minutes": remaining_minutes,
            "remaining_label": _label_minutes(remaining_minutes),
            "completion_percent": percent,
            "status": status,
            "next_module": next_module,
            "badge": {**track["badge"], "earned": status == "completed"},
        }

    # ------------------------------------------------------- public API
    def tracks(self, completed: set[str] | None = None) -> list[dict[str, Any]]:
        completed = completed or set()
        return [self._progress(t, completed) for t in self._build().values()]

    def get_track(self, key: str, completed: set[str] | None = None) -> dict[str, Any]:
        track = self._build().get(key)
        if not track:
            raise NotFoundError("Academy track", key)
        return self._progress(track, completed or set())

    def badges(self, completed: set[str] | None = None) -> list[dict[str, Any]]:
        completed = completed or set()
        out: list[dict[str, Any]] = []
        all_earned = True
        for track in self._build().values():
            prog = self._progress(track, completed)
            earned = prog["status"] == "completed"
            all_earned = all_earned and earned
            out.append({**track["badge"], "earned": earned})
        out.append({**_GRADUATE_BADGE, "earned": all_earned and bool(self._build())})
        return out

    def dashboard(self, completed: set[str] | None = None) -> dict[str, Any]:
        completed = completed or set()
        progressed = [self._progress(t, completed) for t in self._build().values()]
        badges = self.badges(completed)
        unique_modules = {m["key"] for t in self._build().values() for m in t["modules"]}
        total_minutes = sum(t["estimated_minutes"] for t in self._build().values())
        tracks_completed = sum(1 for p in progressed if p["status"] == "completed")
        badges_earned = sum(1 for b in badges if b["earned"])
        overall_percent = (
            round(sum(p["completion_percent"] for p in progressed) / len(progressed))
            if progressed else 0
        )
        return {
            "tracks": progressed,
            "badges": badges,
            "totals": {
                "tracks": len(progressed),
                "modules": len(unique_modules),
                "badges": len(badges),
                "estimated_minutes": total_minutes,
                "estimated_label": _label_minutes(total_minutes),
            },
            "overall": {
                "completion_percent": overall_percent,
                "tracks_completed": tracks_completed,
                "badges_earned": badges_earned,
                "is_graduate": tracks_completed == len(progressed) and bool(progressed),
            },
        }
