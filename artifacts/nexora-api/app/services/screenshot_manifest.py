"""Sprint 56A — ScreenshotManifestService.

Tracks screenshot metadata for every page and workflow across the customer-success
content (modules, journeys, integration playbooks, success center). No binary image
storage — only metadata placeholders.

Each manifest entry exposes:
    page_name, route, screenshot_name, screenshot_category, description, capture_priority
"""

from __future__ import annotations

from typing import Any

from app.services.customer_success_content import (
    JOURNEYS,
    MODULES,
    PLAYBOOKS,
    SCREENSHOT_CATEGORIES,
    SUCCESS_CENTER,
)

# Capture priority by category — drives which screenshots to capture first.
_PRIORITY_BY_CATEGORY = {
    "onboarding": "high",
    "incident": "high",
    "monitoring": "medium",
    "deployment": "medium",
    "reporting": "medium",
    "integrations": "medium",
    "admin": "low",
}


def _priority(category: str) -> str:
    return _PRIORITY_BY_CATEGORY.get(category, "medium")


class ScreenshotManifestService:
    """Builds the screenshot manifest from the customer-success content catalog."""

    def _entry(
        self, *, page_name: str, route: str, screenshot_name: str, category: str, description: str
    ) -> dict[str, Any]:
        return {
            "page_name": page_name,
            "route": route,
            "screenshot_name": screenshot_name,
            "screenshot_category": category,
            "description": description,
            "capture_priority": _priority(category),
        }

    def build(self, *, category: str | None = None) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []

        for module in MODULES:
            route = module["route"]
            for shot in module["screenshots"]:
                entries.append(
                    self._entry(
                        page_name=module["name"],
                        route=route,
                        screenshot_name=shot["name"],
                        category=shot["category"],
                        description=shot["caption"],
                    )
                )

        for journey in JOURNEYS:
            for shot in journey["screenshots"]:
                entries.append(
                    self._entry(
                        page_name=f"Journey: {journey['name']}",
                        route="/documentation",
                        screenshot_name=shot["name"],
                        category=shot["category"],
                        description=shot["caption"],
                    )
                )

        for playbook in PLAYBOOKS:
            for shot in playbook["screenshots"]:
                entries.append(
                    self._entry(
                        page_name=f"Playbook: {playbook['name']}",
                        route="/integrations",
                        screenshot_name=shot["name"],
                        category=shot["category"],
                        description=shot["caption"],
                    )
                )

        for guide in SUCCESS_CENTER:
            for shot in guide["screenshots"]:
                entries.append(
                    self._entry(
                        page_name=f"Success: {guide['name']}",
                        route="/documentation",
                        screenshot_name=shot["name"],
                        category=shot["category"],
                        description=shot["caption"],
                    )
                )

        if category:
            entries = [e for e in entries if e["screenshot_category"] == category]
        return entries

    def summary(self) -> dict[str, Any]:
        entries = self.build()
        by_category: dict[str, int] = {c: 0 for c in SCREENSHOT_CATEGORIES}
        by_priority: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
        for e in entries:
            by_category[e["screenshot_category"]] = by_category.get(e["screenshot_category"], 0) + 1
            by_priority[e["capture_priority"]] = by_priority.get(e["capture_priority"], 0) + 1
        return {
            "total": len(entries),
            "categories": SCREENSHOT_CATEGORIES,
            "by_category": by_category,
            "by_priority": by_priority,
        }
