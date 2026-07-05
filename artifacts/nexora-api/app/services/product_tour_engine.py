"""Sprint 56E.1 - Interactive Product Tours (ProductTourEngine).

Turns the deterministic documentation catalog into guided, in-app learning so a
new customer can learn the platform without reading documentation.

Deterministic and read-only (no DB). It builds:

* One guided tour for every major module (12 modules).
* Three curated cross-module tours: Beginner, Advanced, Executive.

Every tour step carries the required fields:
    step title, description, target UI element, expected result, next action

Lifecycle actions (Start / Resume / Skip / Replay) and progress tracking
(started_at, completed_at, completion_percentage) are computed statelessly from
the client-supplied set of completed step ids - no server-side session needed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.services.customer_success_content import MODULES, get_module

# Major modules that get a dedicated guided tour, in learning order.
TOUR_MODULES: list[str] = [
    "discovery", "monitoring", "incidents", "timeline", "recommendations",
    "remediation", "postmortems", "service-health", "deployment-safety",
    "capacity", "cost", "executive-reports",
]

# Curated cross-module tours (module_key, step_order) picks.
_BEGINNER_PICKS = [
    ("discovery", 1), ("discovery", 2), ("monitoring", 1), ("monitoring", 2),
    ("incidents", 1), ("incidents", 2), ("service-health", 1), ("executive-reports", 1),
]
_ADVANCED_PICKS = [
    ("timeline", 1), ("recommendations", 1), ("remediation", 1), ("remediation", 5),
    ("postmortems", 1), ("deployment-safety", 1), ("capacity", 1), ("cost", 1),
]
_EXECUTIVE_PICKS = [
    ("executive-reports", 1), ("executive-reports", 2), ("service-health", 1),
    ("capacity", 1), ("cost", 1),
]

_VALID_ACTIONS = {"start", "resume", "skip", "replay", "progress"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _title(action: str) -> str:
    """Short, human title derived from a step's action sentence."""
    text = str(action).strip()
    for sep in (". ", " - ", ": "):
        if sep in text:
            text = text.split(sep, 1)[0]
            break
    text = text.rstrip(".")
    words = text.split()
    if len(words) > 8:
        text = " ".join(words[:8]) + "…"
    return text


def _module_index(module: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {s["order"]: s for s in module.get("steps", [])}


class ProductTourEngine:
    """Deterministic catalog of interactive product tours + lifecycle tracking."""

    def __init__(self) -> None:
        self._tours: dict[str, dict[str, Any]] = {}
        self._build()

    # ------------------------------------------------------------- building
    def _tour_step(
        self, *, order: int, module: dict[str, Any], src: dict[str, Any],
        next_title: str | None, last_next_action: str,
    ) -> dict[str, Any]:
        screens = src.get("expected_screens") or module.get("expected_screens") or []
        target_element = screens[(order - 1) % len(screens)] if screens else module["name"]
        next_action = f"Next: {next_title}" if next_title else last_next_action
        return {
            "order": order,
            "title": _title(src["action"]),
            "description": src["action"],
            "detail": src.get("internal", ""),
            "module": module["key"],
            "target_element": target_element,
            "target_route": module["route"],
            "target_selector": f"[data-tour='{module['key']}-{src['order']}']",
            "expected_result": src["expected"],
            "next_action": next_action,
            "screenshot": src.get("screenshot", ""),
            "screenshot_id": src.get("screenshot_id", ""),
        }

    def _build_module_tour(self, module_key: str) -> dict[str, Any] | None:
        module = get_module(module_key)
        if not module:
            return None
        src_steps = module.get("steps", [])
        next_steps = module.get("next_steps") or []
        last_next = f"Next: {next_steps[0]}" if next_steps else "Finish the tour"
        steps: list[dict[str, Any]] = []
        for i, src in enumerate(src_steps, start=1):
            nxt = src_steps[i]["action"] if i < len(src_steps) else None
            steps.append(self._tour_step(
                order=i, module=module, src=src,
                next_title=_title(nxt) if nxt else None, last_next_action=last_next,
            ))
        return {
            "key": f"tour-{module_key}",
            "name": f"{module['name']} Tour",
            "kind": "module",
            "module": module_key,
            "audience": "all",
            "difficulty": module.get("metadata", {}).get("difficulty", "Beginner"),
            "summary": module.get("overview", {}).get("what", ""),
            "estimated_minutes": max(2, len(steps)),
            "steps": steps,
        }

    def _build_variant_tour(
        self, *, key: str, name: str, difficulty: str, audience: str,
        summary: str, picks: list[tuple[str, int]],
    ) -> dict[str, Any]:
        # Resolve each pick to a (module, src_step) pair first.
        resolved: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for module_key, order in picks:
            module = get_module(module_key)
            if not module:
                continue
            src = _module_index(module).get(order)
            if src:
                resolved.append((module, src))
        steps: list[dict[str, Any]] = []
        for i, (module, src) in enumerate(resolved, start=1):
            if i < len(resolved):
                nxt_module, nxt_src = resolved[i]
                next_title = f"{nxt_module['name']} — {_title(nxt_src['action'])}"
            else:
                next_title = None
            steps.append(self._tour_step(
                order=i, module=module, src=src,
                next_title=next_title, last_next_action="Finish the tour",
            ))
        return {
            "key": key,
            "name": name,
            "kind": "variant",
            "module": "multi",
            "audience": audience,
            "difficulty": difficulty,
            "summary": summary,
            "estimated_minutes": max(2, len(steps)),
            "steps": steps,
        }

    def _build(self) -> None:
        for module_key in TOUR_MODULES:
            tour = self._build_module_tour(module_key)
            if tour:
                self._tours[tour["key"]] = tour
        variants = [
            self._build_variant_tour(
                key="tour-beginner", name="Beginner Tour", difficulty="Beginner",
                audience="beginner",
                summary="A gentle first walkthrough: connect, watch, and handle your first incident.",
                picks=_BEGINNER_PICKS,
            ),
            self._build_variant_tour(
                key="tour-advanced", name="Advanced Tour", difficulty="Advanced",
                audience="sre",
                summary="Go deep: investigate, recommend, remediate, retrospect, and ship safely.",
                picks=_ADVANCED_PICKS,
            ),
            self._build_variant_tour(
                key="tour-executive", name="Executive Tour", difficulty="Beginner",
                audience="executive",
                summary="The leadership view: reliability, cost, capacity, and exportable reports.",
                picks=_EXECUTIVE_PICKS,
            ),
        ]
        for v in variants:
            self._tours[v["key"]] = v

    # ------------------------------------------------------------- read API
    def list_tours(self, *, kind: str | None = None, audience: str | None = None) -> dict[str, Any]:
        tours = list(self._tours.values())
        if kind:
            tours = [t for t in tours if t["kind"] == kind]
        if audience:
            tours = [t for t in tours if t["audience"] == audience]
        items = [
            {
                "key": t["key"], "name": t["name"], "kind": t["kind"], "module": t["module"],
                "audience": t["audience"], "difficulty": t["difficulty"], "summary": t["summary"],
                "estimated_minutes": t["estimated_minutes"], "step_count": len(t["steps"]),
            }
            for t in tours
        ]
        return {"items": items, "total": len(items)}

    def all_tours(self) -> list[dict[str, Any]]:
        return list(self._tours.values())

    def get_tour(self, key: str) -> dict[str, Any] | None:
        return self._tours.get(key)

    def tours_for_module(self, module: str) -> dict[str, Any]:
        items = [t for t in self._tours.values() if t["module"] == module]
        return {"items": items, "total": len(items)}

    def _step_ids(self, tour: dict[str, Any]) -> list[str]:
        return [f"{tour['key']}-step-{s['order']}" for s in tour["steps"]]

    # ------------------------------------------------------------- lifecycle
    def state(
        self, key: str, *, action: str = "progress",
        completed: list[str] | None = None, started_at: str | None = None,
    ) -> dict[str, Any] | None:
        tour = self.get_tour(key)
        if not tour:
            return None
        action = (action or "progress").lower()
        if action not in _VALID_ACTIONS:
            action = "progress"
        all_ids = self._step_ids(tour)
        total = len(all_ids)
        completed = [c for c in (completed or []) if c in all_ids]

        # Start / Replay reset progress.
        if action in ("start", "replay"):
            completed = []
            started_at = _now()
        elif started_at is None:
            started_at = _now()

        percent = round(len(completed) / total * 100) if total else 0
        # Current step = first not-yet-completed step.
        current_index = next((i for i, sid in enumerate(all_ids) if sid not in completed), total)

        completed_at: str | None = None
        if action == "skip":
            status = "skipped"
            completed_at = _now()
        elif len(completed) >= total and total > 0:
            status = "completed"
            percent = 100
            current_index = total
            completed_at = _now()
        elif action in ("start", "replay"):
            status = "in_progress"
        else:
            status = "in_progress"

        current_step = tour["steps"][current_index] if current_index < total else None
        return {
            "key": tour["key"],
            "name": tour["name"],
            "action": action,
            "status": status,
            "total_steps": total,
            "completed_steps": len(completed),
            "completed_step_ids": completed,
            "completion_percentage": percent,
            "current_step_index": current_index,
            "current_step": current_step,
            "started_at": started_at,
            "completed_at": completed_at,
        }


# Module-coverage sanity: every documented major module has a tour module key.
_DOC_MODULE_KEYS = {m["key"] for m in MODULES}
TOUR_MODULES_PRESENT = [k for k in TOUR_MODULES if k in _DOC_MODULE_KEYS]
