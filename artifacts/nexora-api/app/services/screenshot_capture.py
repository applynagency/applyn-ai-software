"""Sprint 56B — ScreenshotCaptureService.

Generates deterministic screenshot *metadata* for every customer-facing page
across device modes and capture types. No binary images are produced or stored —
this models a capture pipeline so documentation, galleries, and coverage reports
have stable, addressable screenshot references.

Each capture entry exposes:
    id, page_name, route, module, category, device, capture_type,
    screenshot_path, captured, captured_at, version
"""

from __future__ import annotations

from typing import Any

VERSION = "v1"
CAPTURED_AT = "2026-06-23T00:00:00Z"

DEVICES = ["desktop", "tablet", "mobile"]
CAPTURE_TYPES = ["full_page", "widget", "workflow_step", "modal", "dashboard"]

# Customer-facing areas (Sprint 56B deliverable 1).
# (page_name, route, module, category)
SUPPORTED_AREAS: list[tuple[str, str, str, str]] = [
    ("Dashboard", "/", "dashboard", "reporting"),
    ("Monitoring", "/monitoring", "monitoring", "monitoring"),
    ("Incident Intelligence", "/incidents", "incidents", "incident"),
    ("Timeline", "/incidents", "incidents", "incident"),
    ("Change Intelligence", "/incidents", "incidents", "incident"),
    ("Recommendations", "/incidents", "incidents", "incident"),
    ("Remediation", "/incidents", "incidents", "incident"),
    ("Postmortems", "/postmortems", "postmortems", "incident"),
    ("Service Health", "/services", "service-health", "monitoring"),
    ("Capacity Planning", "/capacity", "capacity", "reporting"),
    ("Cost Optimization", "/cost", "cost", "reporting"),
    ("Deployment Risk", "/deployment-risk", "change-failure", "deployment"),
    ("Deployment Safety", "/deployment-safety", "deployment-safety", "deployment"),
    ("Change Failure Prediction", "/change-failure", "change-failure", "deployment"),
    ("Reports", "/reports", "executive-reports", "reporting"),
    ("Documentation", "/documentation", "documentation", "admin"),
    ("Demo Center", "/demo-organizations", "demo", "admin"),
]

_DASHBOARD_PAGES = {"Dashboard", "Reports", "Service Health"}
_WORKFLOW_PAGES = {
    "Timeline", "Change Intelligence", "Recommendations", "Remediation",
    "Deployment Risk", "Deployment Safety", "Change Failure Prediction",
}
_MODAL_PAGES = {"Incident Intelligence", "Remediation", "Cost Optimization"}


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-").replace("--", "-")


def _area_types(page_name: str) -> list[str]:
    types = ["full_page", "widget"]
    if page_name in _DASHBOARD_PAGES:
        types.append("dashboard")
    if page_name in _WORKFLOW_PAGES:
        types.append("workflow_step")
    if page_name in _MODAL_PAGES:
        types.append("modal")
    return types


def _captured(device: str, capture_type: str) -> bool:
    """Deterministic capture registry — modal screens are not yet captured on
    mobile (the remaining visual-coverage work), everything else is captured."""
    return not (device == "mobile" and capture_type == "modal")


class ScreenshotCaptureService:
    def _entry(self, *, page_name: str, route: str, module: str, category: str,
               device: str, capture_type: str) -> dict[str, Any]:
        slug = _slug(page_name)
        name = f"{slug}-{capture_type}-{device}"
        return {
            "id": name,
            "page_name": page_name,
            "route": route,
            "module": module,
            "category": category,
            "device": device,
            "capture_type": capture_type,
            "screenshot_path": f"/static/screenshots/{VERSION}/{device}/{capture_type}/{slug}.png",
            "captured": _captured(device, capture_type),
            "captured_at": CAPTURED_AT,
            "version": VERSION,
        }

    def build(self, *, device: str | None = None, module: str | None = None,
              capture_type: str | None = None) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for page_name, route, mod, category in SUPPORTED_AREAS:
            for ctype in _area_types(page_name):
                for dev in DEVICES:
                    entries.append(self._entry(
                        page_name=page_name, route=route, module=mod,
                        category=category, device=dev, capture_type=ctype))
        if device:
            entries = [e for e in entries if e["device"] == device]
        if module:
            entries = [e for e in entries if e["module"] == module]
        if capture_type:
            entries = [e for e in entries if e["capture_type"] == capture_type]
        return entries

    def _coverage(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(entries)
        captured = sum(1 for e in entries if e["captured"])
        return {
            "total": total,
            "captured": captured,
            "missing": total - captured,
            "coverage_percent": round(captured / total * 100) if total else 0,
        }

    def _group(self, entries: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
        names = []
        seen = set()
        for e in entries:
            if e[key] not in seen:
                seen.add(e[key])
                names.append(e[key])
        out = []
        for name in names:
            grp = [e for e in entries if e[key] == name]
            out.append({"name": name, **self._coverage(grp)})
        return out

    def summary(self) -> dict[str, Any]:
        entries = self.build()
        return {
            "platform": self._coverage(entries),
            "by_device": self._group(entries, "device"),
            "by_module": self._group(entries, "module"),
            "by_category": self._group(entries, "category"),
            "by_capture_type": self._group(entries, "capture_type"),
            "devices": DEVICES,
            "capture_types": CAPTURE_TYPES,
            "version": VERSION,
        }
