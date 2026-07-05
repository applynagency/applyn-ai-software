"""Sprint 56C — UI registry (documentation reality source of truth).

A deterministic snapshot of the *actual* application's routes and pages, mirrored
from the frontend navigation (``nexora-web/src/lib/navigation.tsx``) plus the
drill-down and standalone routes wired in ``App.tsx``. Documentation verification,
drift detection, and navigation validation compare documented references against
this registry. Read-only, no DB.
"""

from __future__ import annotations

from typing import Any

# Current UI build version. Documentation screenshots captured against an older
# version are flagged OUTDATED by the verification engine.
UI_VERSION = "2026.06"

# route -> {title, module}. Mirrors the live frontend.
PAGES: dict[str, dict[str, str]] = {
    "/": {"title": "Executive Dashboard", "module": "executive-reports"},
    "/monitoring": {"title": "Monitoring", "module": "monitoring"},
    "/incidents": {"title": "Incidents", "module": "incidents"},
    "/incidents/:id": {"title": "Incident Detail", "module": "incidents"},
    "/war-rooms": {"title": "War Rooms", "module": "incidents"},
    "/postmortems": {"title": "Postmortems", "module": "postmortems"},
    "/services": {"title": "Services", "module": "service-health"},
    "/services/:id": {"title": "Service Detail", "module": "service-health"},
    "/slos": {"title": "SLOs", "module": "slos"},
    "/dependencies": {"title": "Dependency Graph", "module": "dependencies"},
    "/service-health": {"title": "Service Health", "module": "service-health"},
    "/discovery": {"title": "Discovery", "module": "onboarding"},
    "/integrations": {"title": "Integrations", "module": "onboarding"},
    "/capacity": {"title": "Capacity Planning", "module": "capacity"},
    "/cost": {"title": "Cost Optimization", "module": "cost"},
    "/deployment-safety": {"title": "Deployment Safety", "module": "deployment-safety"},
    "/deployment-risk": {"title": "Deployment Risk", "module": "change-failure"},
    "/change-failure": {"title": "Change Failure Prediction", "module": "change-failure"},
    "/ai-teams": {"title": "Teams", "module": "executive-reports"},
    "/agents": {"title": "Agents", "module": "executive-reports"},
    "/workflows": {"title": "Workflows", "module": "executive-reports"},
    "/memory": {"title": "Memory", "module": "executive-reports"},
    "/reports": {"title": "Executive Reports", "module": "executive-reports"},
    "/roi": {"title": "ROI", "module": "executive-reports"},
    "/documentation": {"title": "Documentation", "module": "executive-reports"},
    "/demo-organizations": {"title": "Demo Organizations", "module": "demo"},
    "/demo-scenarios": {"title": "Demo Scenarios", "module": "demo"},
    "/product-tours": {"title": "Product Tours", "module": "demo"},
    "/credentials": {"title": "Credentials", "module": "onboarding"},
    "/users": {"title": "Users", "module": "onboarding"},
    "/roles": {"title": "Roles", "module": "onboarding"},
    "/audit-logs": {"title": "Audit Logs", "module": "onboarding"},
    "/onboarding": {"title": "Get Started", "module": "onboarding"},
    "/executive-command-center": {"title": "Executive Command Center", "module": "executive-reports"},
}

ROUTES = set(PAGES.keys())

# Modules that exist in the product (documentation module keys + infra ones).
PRESENT_MODULES = {
    "onboarding", "monitoring", "incidents", "postmortems", "service-health",
    "slos", "dependencies", "capacity", "cost", "deployment-safety",
    "change-failure", "executive-reports", "demo", "documentation", "dashboard",
}


def route_exists(route: str) -> bool:
    return route in ROUTES


def page_for(route: str) -> dict[str, Any] | None:
    return PAGES.get(route)


def module_present(module: str) -> bool:
    return module in PRESENT_MODULES
