"""Status page helpers (Sprint 65C)."""

from __future__ import annotations


def build_public_view(page: dict, components: list[dict], incidents: list[dict]) -> dict:
    """Assemble RSS/JSON-friendly status page payload."""
    overall = _overall_status(components)
    return {
        "page": {
            "name": page.get("name"),
            "slug": page.get("slug"),
            "visibility": page.get("visibility", "PUBLIC"),
            "branding": page.get("branding") or {},
        },
        "status": overall,
        "components": [
            {
                "name": c.get("name"),
                "status": c.get("status", "OPERATIONAL"),
                "description": c.get("description"),
            }
            for c in components
        ],
        "incidents": [
            {
                "title": i.get("title"),
                "status": i.get("status"),
                "impact": i.get("impact"),
                "started_at": str(i.get("started_at", "")),
                "updates": i.get("updates") or [],
            }
            for i in incidents[:20]
        ],
    }


def _overall_status(components: list[dict]) -> str:
    order = {"MAJOR_OUTAGE": 4, "PARTIAL_OUTAGE": 3, "DEGRADED": 2, "MAINTENANCE": 1, "OPERATIONAL": 0}
    worst = "OPERATIONAL"
    for c in components:
        st = (c.get("status") or "OPERATIONAL").upper()
        if order.get(st, 0) > order.get(worst, 0):
            worst = st
    return worst
