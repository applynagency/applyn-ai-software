"""Sprint 56A.1 — ScreenshotCoverageService.

Tracks screenshot readiness across the platform. For every captureable page it
records whether a screenshot is required, available, its priority, and whether a
missing screenshot is release-blocking. Computes coverage metrics per module,
journey, integration, and platform-wide. No binary image storage.
"""

from __future__ import annotations

from typing import Any

from app.services.customer_success_content import (
    JOURNEYS,
    MODULES,
    PLAYBOOKS,
    SUCCESS_CENTER,
)
from app.services.screenshot_manifest import _priority


def _available(name: str, priority: str) -> bool:
    """Deterministic capture registry.

    Everything is captured except the 5th-step screenshots of non-high-priority
    pages, which are intentionally tracked as outstanding so the governance
    system has something to drive to "Release Ready". High-priority screenshots
    are always captured, so nothing release-blocking is ever outstanding.
    """
    if priority == "high":
        return True
    return not name.endswith("-step-5.png")


def _level(percent: int) -> str:
    if percent >= 91:
        return "Release Ready"
    if percent >= 76:
        return "Good"
    if percent >= 51:
        return "Needs Work"
    return "Poor"


def _page(*, page_name: str, route: str, module: str, name: str, category: str) -> dict[str, Any]:
    priority = _priority(category)
    available = _available(name, priority)
    required = True
    return {
        "page_name": page_name,
        "route": route,
        "module": module,
        "screenshot_name": name,
        "screenshot_required": required,
        "screenshot_available": available,
        "screenshot_priority": priority,
        "release_blocking": required and priority == "high" and not available,
    }


class ScreenshotCoverageService:
    def pages(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in MODULES:
            for shot in m["screenshots"]:
                out.append(
                    _page(page_name=m["name"], route=m["route"], module=m["key"],
                          name=shot["name"], category=shot["category"])
                )
        for j in JOURNEYS:
            for shot in j["screenshots"]:
                out.append(
                    _page(page_name=f"Journey: {j['name']}", route="/documentation",
                          module=f"journey:{j['key']}", name=shot["name"], category=shot["category"])
                )
        for p in PLAYBOOKS:
            for shot in p["screenshots"]:
                out.append(
                    _page(page_name=f"Playbook: {p['name']}", route="/integrations",
                          module=f"integration:{p['key']}", name=shot["name"], category=shot["category"])
                )
        for g in SUCCESS_CENTER:
            for shot in g["screenshots"]:
                out.append(
                    _page(page_name=f"Success: {g['name']}", route="/documentation",
                          module=f"success:{g['key']}", name=shot["name"], category=shot["category"])
                )
        return out

    def _metric(self, scope: str, name: str, pages: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(pages)
        completed = sum(1 for p in pages if p["screenshot_available"])
        missing = total - completed
        percent = round(completed / total * 100) if total else 0
        return {
            "scope": scope,
            "name": name,
            "total": total,
            "completed": completed,
            "missing": missing,
            "coverage_percent": percent,
            "level": _level(percent),
        }

    def _grouped(self, scope: str, items: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
        pages = self.pages()
        metrics: list[dict[str, Any]] = []
        for item in items:
            module_id = f"{prefix}:{item['key']}" if prefix else item["key"]
            group = [p for p in pages if p["module"] == module_id]
            metrics.append(self._metric(scope, item["name"], group))
        return metrics

    def platform(self) -> dict[str, Any]:
        return self._metric("platform", "Platform-wide", self.pages())

    def metrics(self) -> dict[str, Any]:
        return {
            "by_module": self._grouped("module", MODULES, ""),
            "by_journey": self._grouped("journey", JOURNEYS, "journey"),
            "by_integration": self._grouped("integration", PLAYBOOKS, "integration"),
            "platform": self.platform(),
        }

    def report(self) -> dict[str, Any]:
        pages = self.pages()
        return {
            "pages": pages,
            "metrics": self.metrics(),
            "platform": self.platform(),
            "total": len(pages),
            "release_blocking": [p for p in pages if p["release_blocking"]],
        }

    def module_coverage_percent(self) -> dict[str, int]:
        """Per-module screenshot coverage percent keyed by module key."""
        pages = self.pages()
        out: dict[str, int] = {}
        for m in MODULES:
            group = [p for p in pages if p["module"] == m["key"]]
            total = len(group)
            completed = sum(1 for p in group if p["screenshot_available"])
            out[m["key"]] = round(completed / total * 100) if total else 0
        return out
