"""Sprint 56D.1 — Real Screenshot Asset Generation.

Generates *actual* renderable screenshot image assets (deterministic, dependency
-free SVG mockups of each customer-facing page) so documentation articles render
real images instead of empty placeholders.

Every asset maps to a real route in the UI registry (validated). Assets are
written under ``assets/documentation/screenshots/`` and can also be rendered
on demand by ``screenshot_id`` or by ``route``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.services.ui_registry import PAGES, route_exists

CAPTURE_DATE = "2026-06-23"
ASSET_VERSION = "1.0"

DEVICES = ["desktop", "tablet", "mobile"]
SHOTS = ["overview", "detail", "workflow"]

# Customer-facing areas → (slug, page_name, route, title, description).
# Each route is validated against the UI registry.
AREAS: list[dict[str, str]] = [
    {"slug": "dashboard", "page_name": "Dashboard", "route": "/",
     "title": "Executive Dashboard", "description": "Reliability posture at a glance."},
    {"slug": "applications", "page_name": "Applications", "route": "/services",
     "title": "Applications", "description": "Service and application catalog."},
    {"slug": "ai-teams", "page_name": "AI Teams", "route": "/ai-teams",
     "title": "AI Teams", "description": "Autonomous SRE teams and agents."},
    {"slug": "workflows", "page_name": "Workflows", "route": "/workflows",
     "title": "Workflows", "description": "Automated investigation and remediation workflows."},
    {"slug": "monitoring", "page_name": "Monitoring", "route": "/monitoring",
     "title": "Monitoring", "description": "Live alerts and signal health."},
    {"slug": "incidents", "page_name": "Incidents", "route": "/incidents",
     "title": "Incidents", "description": "Active and resolved incidents."},
    {"slug": "incident-detail", "page_name": "Incident Detail", "route": "/incidents/:id",
     "title": "Incident Detail", "description": "Root cause, confidence, and impact."},
    {"slug": "timeline", "page_name": "Timeline", "route": "/incidents/:id",
     "title": "Incident Timeline", "description": "Chronological event reconstruction."},
    {"slug": "recommendations", "page_name": "Recommendations", "route": "/incidents/:id",
     "title": "Recommendations", "description": "Ranked remediation recommendations."},
    {"slug": "remediation", "page_name": "Remediation", "route": "/incidents/:id",
     "title": "Remediation", "description": "Approvals and execution results."},
    {"slug": "postmortems", "page_name": "Postmortems", "route": "/postmortems",
     "title": "Postmortems", "description": "Generated incident postmortems."},
    {"slug": "service-health", "page_name": "Service Health", "route": "/service-health",
     "title": "Service Health", "description": "Availability, burn rate, and budget."},
    {"slug": "service-dependencies", "page_name": "Service Dependencies", "route": "/dependencies",
     "title": "Service Dependencies", "description": "Dependency graph and blast radius."},
    {"slug": "slos", "page_name": "SLOs & Error Budgets", "route": "/slos",
     "title": "SLOs & Error Budgets", "description": "Service level objectives and error budgets."},
    {"slug": "deployment-risk", "page_name": "Deployment Risk", "route": "/deployment-risk",
     "title": "Deployment Risk", "description": "Risk scoring for upcoming deploys."},
    {"slug": "deployment-safety", "page_name": "Deployment Safety", "route": "/deployment-safety",
     "title": "Deployment Safety", "description": "Safety gates and guardrails."},
    {"slug": "change-failure-prediction", "page_name": "Change Failure Prediction",
     "route": "/change-failure", "title": "Change Failure Prediction",
     "description": "Predicted change failure probability."},
    {"slug": "capacity-planning", "page_name": "Capacity Planning", "route": "/capacity",
     "title": "Capacity Planning", "description": "Forecasts and saturation risk."},
    {"slug": "cost-optimization", "page_name": "Cost Optimization", "route": "/cost",
     "title": "Cost Optimization", "description": "Savings opportunities and FinOps."},
    {"slug": "reports", "page_name": "Reports", "route": "/reports",
     "title": "Executive Reports", "description": "Leadership reliability reports."},
    {"slug": "documentation", "page_name": "Documentation", "route": "/documentation",
     "title": "Documentation", "description": "Guides, playbooks, and screenshots."},
    {"slug": "demo-center", "page_name": "Demo Center", "route": "/demo-organizations",
     "title": "Demo Center", "description": "Demo organizations and scenarios."},
    {"slug": "executive-command-center", "page_name": "Executive Command Center",
     "route": "/executive-command-center", "title": "Executive Command Center",
     "description": "Unified executive reliability command center."},
    {"slug": "infrastructure-discovery", "page_name": "Infrastructure Discovery",
     "route": "/discovery", "title": "Infrastructure Discovery",
     "description": "Discovered assets across providers."},
    {"slug": "onboarding-wizard", "page_name": "Onboarding Wizard", "route": "/onboarding",
     "title": "Onboarding Wizard", "description": "Guided first-value onboarding."},
    {"slug": "integrations", "page_name": "Integrations", "route": "/integrations",
     "title": "Integrations", "description": "Cloud, source, and alerting integrations."},
]

# Theme.
_BG = "#0b1020"
_PANEL = "#141a2e"
_PANEL2 = "#1b2440"
_BORDER = "#2a355c"
_TEXT = "#e2e8f0"
_MUTED = "#94a3b8"
_VIOLET = "#8b5cf6"
_EMERALD = "#34d399"
_SKY = "#38bdf8"
_AMBER = "#fbbf24"

_DIMS = {"desktop": (1280, 800), "tablet": (834, 1120), "mobile": (390, 844)}
_NAV = ["Dashboard", "Monitoring", "Incidents", "Services", "Capacity", "Cost", "Reports"]


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _seed(key: str) -> int:
    return int(hashlib.md5(key.encode()).hexdigest(), 16)


def _bars(key: str, count: int) -> list[int]:
    s = _seed(key)
    out = []
    for i in range(count):
        out.append(30 + (s >> (i * 5)) % 70)
    return out


class ScreenshotAssetGenerator:
    def __init__(self, base_dir: Path | None = None) -> None:
        if base_dir is None:
            # app/services/screenshot_assets.py -> nexora-api/
            base_dir = Path(__file__).resolve().parents[2] / "assets" / "documentation" / "screenshots"
        self.base_dir = base_dir

    # -- manifest ---------------------------------------------------------- #
    def _entry(self, area: dict[str, str], shot: str, device: str) -> dict[str, Any]:
        sid = f"{area['slug']}-{shot}-{device}"
        return {
            "screenshot_id": sid,
            "page_name": area["page_name"],
            "route": area["route"],
            "title": area["title"],
            "description": area["description"],
            "device": device,
            "shot_type": shot,
            "capture_date": CAPTURE_DATE,
            "version": ASSET_VERSION,
            "path": f"assets/documentation/screenshots/{sid}.svg",
            "asset_url": f"/nexora-api/v1/customer-success/screenshots/{sid}",
            "route_valid": route_exists(area["route"]),
        }

    def manifest(self) -> list[dict[str, Any]]:
        out = []
        for area in AREAS:
            for shot in SHOTS:
                for device in DEVICES:
                    out.append(self._entry(area, shot, device))
        return out

    def coverage(self) -> dict[str, Any]:
        entries = self.manifest()
        total = len(entries)
        valid = sum(1 for e in entries if e["route_valid"])
        return {
            "total": total,
            "valid": valid,
            "invalid": total - valid,
            "coverage_percent": round(valid / total * 100) if total else 0,
            "areas": len(AREAS),
            "devices": len(DEVICES),
            "shots": len(SHOTS),
        }

    def _area_by_slug(self, slug: str) -> dict[str, str] | None:
        for a in AREAS:
            if a["slug"] == slug:
                return a
        return None

    # -- generation (writes real files) ------------------------------------ #
    def generate(self) -> dict[str, Any]:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        written = 0
        for entry in self.manifest():
            if not entry["route_valid"]:
                continue
            area = self._area_by_slug(entry["screenshot_id"].rsplit("-", 2)[0]) or {}
            svg = self._svg(
                title=entry["title"], route=entry["route"],
                shot=entry["shot_type"], device=entry["device"],
                description=area.get("description", ""), key=entry["screenshot_id"],
            )
            (self.base_dir / f"{entry['screenshot_id']}.svg").write_text(svg, encoding="utf-8")
            written += 1
        return {"generated": written, "directory": str(self.base_dir), **self.coverage()}

    # -- rendering --------------------------------------------------------- #
    def svg_for_id(self, screenshot_id: str) -> str:
        # Prefer the canonical area mapping when the id is well-formed.
        parts = screenshot_id.rsplit("-", 2)
        slug = parts[0] if parts else screenshot_id
        shot = parts[1] if len(parts) == 3 and parts[1] in SHOTS else "overview"
        device = parts[2] if len(parts) == 3 and parts[2] in DEVICES else "desktop"
        area = self._area_by_slug(slug)
        if area:
            return self._svg(title=area["title"], route=area["route"], shot=shot,
                             device=device, description=area["description"], key=screenshot_id)
        # Fallback: render a generic but real image so no placeholder is shown.
        title = slug.replace("-", " ").title()
        return self._svg(title=title, route="/", shot=shot, device=device,
                         description="Platform screen", key=screenshot_id)

    def svg_for_route(self, route: str, shot: str = "overview", device: str = "desktop") -> str:
        shot = shot if shot in SHOTS else "overview"
        device = device if device in DEVICES else "desktop"
        for a in AREAS:
            if a["route"] == route:
                return self._svg(title=a["title"], route=route, shot=shot, device=device,
                                 description=a["description"], key=f"{a['slug']}-{shot}-{device}")
        page = PAGES.get(route, {})
        title = page.get("title", route.strip("/").title() or "Dashboard")
        return self._svg(title=title, route=route, shot=shot, device=device,
                         description="Platform screen", key=f"{route}-{shot}-{device}")

    # -- SVG builder ------------------------------------------------------- #
    def _svg(self, *, title: str, route: str, shot: str, device: str,
             description: str, key: str) -> str:
        w, h = _DIMS.get(device, _DIMS["desktop"])
        compact = device != "desktop"
        body = self._content(title, shot, device, key, description)
        chrome = self._chrome(w, route, device, title, compact)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" font-family="Inter,Segoe UI,system-ui,sans-serif">'
            f'<rect width="{w}" height="{h}" rx="14" fill="{_BG}"/>'
            f'{chrome}{body}'
            f'</svg>'
        )

    def _chrome(self, w: int, route: str, device: str, title: str, compact: bool) -> str:
        bar = (
            f'<rect x="0" y="0" width="{w}" height="40" rx="14" fill="{_PANEL2}"/>'
            f'<rect x="0" y="20" width="{w}" height="20" fill="{_PANEL2}"/>'
            f'<circle cx="22" cy="20" r="6" fill="#ef4444"/>'
            f'<circle cx="42" cy="20" r="6" fill="{_AMBER}"/>'
            f'<circle cx="62" cy="20" r="6" fill="{_EMERALD}"/>'
            f'<rect x="92" y="11" width="{w - 130}" height="18" rx="9" fill="{_BG}" stroke="{_BORDER}"/>'
            f'<text x="104" y="24" fill="{_MUTED}" font-size="11">nexora.app{_esc(route)}</text>'
        )
        if compact:
            bar += (
                f'<rect x="14" y="52" width="{w - 28}" height="34" rx="8" fill="{_PANEL}" stroke="{_BORDER}"/>'
                f'<rect x="26" y="63" width="16" height="3" rx="1.5" fill="{_MUTED}"/>'
                f'<rect x="26" y="69" width="16" height="3" rx="1.5" fill="{_MUTED}"/>'
                f'<text x="56" y="74" fill="{_TEXT}" font-size="14" font-weight="600">{_esc(title)}</text>'
            )
        return bar

    def _content(self, title: str, shot: str, device: str, key: str, description: str) -> str:
        compact = device != "desktop"
        if compact:
            cx, cy, cw = 14, 98, _DIMS[device][0] - 28
        else:
            cx, cy, cw = 230, 56, _DIMS["desktop"][0] - 230 - 24
        sidebar = "" if compact else self._sidebar(title)
        header = (
            f'<text x="{cx}" y="{cy + 22}" fill="{_TEXT}" font-size="{18 if compact else 22}" '
            f'font-weight="700">{_esc(title)}</text>'
            f'<text x="{cx}" y="{cy + 42}" fill="{_MUTED}" font-size="12">{_esc(description)}</text>'
        )
        top = cy + 60
        if shot == "overview":
            inner = self._overview(cx, top, cw, key, compact)
        elif shot == "detail":
            inner = self._detail(cx, top, cw, key, compact)
        else:
            inner = self._workflow(cx, top, cw, key, compact)
        return sidebar + header + inner

    def _sidebar(self, title: str) -> str:
        out = [f'<rect x="0" y="40" width="210" height="760" fill="{_PANEL}"/>']
        out.append(f'<text x="24" y="74" fill="{_VIOLET}" font-size="15" font-weight="700">Nexora</text>')
        for i, item in enumerate(_NAV):
            y = 100 + i * 40
            active = item.lower() in title.lower() or (item == "Dashboard" and "dashboard" in title.lower())
            if active:
                out.append(f'<rect x="12" y="{y - 18}" width="186" height="32" rx="8" fill="{_VIOLET}" opacity="0.18"/>')
            color = _TEXT if active else _MUTED
            out.append(f'<circle cx="30" cy="{y - 2}" r="4" fill="{_VIOLET if active else _BORDER}"/>')
            out.append(f'<text x="46" y="{y + 2}" fill="{color}" font-size="13">{_esc(item)}</text>')
        return "".join(out)

    def _overview(self, x: int, y: int, w: int, key: str, compact: bool) -> str:
        cols = 2 if compact else 4
        gap = 12
        cwd = (w - gap * (cols - 1)) // cols
        labels = ["Reliability", "Open Incidents", "MTTR", "SLO Compliance"]
        vals = ["99.2%", "3", "18m", "97%"]
        accents = [_EMERALD, _AMBER, _SKY, _VIOLET]
        out = []
        for i in range(cols if compact else 4):
            px = x + (i % cols) * (cwd + gap)
            py = y + (i // cols) * 78
            out.append(f'<rect x="{px}" y="{py}" width="{cwd}" height="66" rx="10" fill="{_PANEL}" stroke="{_BORDER}"/>')
            out.append(f'<text x="{px + 12}" y="{py + 24}" fill="{_MUTED}" font-size="11">{labels[i]}</text>')
            out.append(f'<text x="{px + 12}" y="{py + 48}" fill="{accents[i]}" font-size="20" font-weight="700">{vals[i]}</text>')
        chart_y = y + (78 * (2 if compact else 1)) + 8
        ch = 150
        out.append(f'<rect x="{x}" y="{chart_y}" width="{w}" height="{ch}" rx="10" fill="{_PANEL}" stroke="{_BORDER}"/>')
        out.append(f'<text x="{x + 14}" y="{chart_y + 24}" fill="{_TEXT}" font-size="13" font-weight="600">Trend</text>')
        bars = _bars(key, 8)
        bw = (w - 40) // len(bars)
        base = chart_y + ch - 16
        for i, b in enumerate(bars):
            bh = int(b / 100 * (ch - 50))
            bx = x + 16 + i * bw
            out.append(f'<rect x="{bx}" y="{base - bh}" width="{bw - 8}" height="{bh}" rx="4" fill="{_SKY}" opacity="0.8"/>')
        return "".join(out)

    def _detail(self, x: int, y: int, w: int, key: str, compact: bool) -> str:
        out = []
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="70" rx="10" fill="{_PANEL}" stroke="{_BORDER}"/>')
        out.append(f'<rect x="{x + 14}" y="{y + 16}" width="64" height="20" rx="10" fill="{_EMERALD}" opacity="0.2"/>')
        out.append(f'<text x="{x + 22}" y="{y + 30}" fill="{_EMERALD}" font-size="11" font-weight="700">VERIFIED</text>')
        out.append(f'<text x="{x + 90}" y="{y + 30}" fill="{_TEXT}" font-size="14" font-weight="600">Root cause identified</text>')
        out.append(f'<text x="{x + 14}" y="{y + 56}" fill="{_MUTED}" font-size="11">Confidence 94% · Impact: 2 services</text>')
        ty = y + 84
        if compact:
            panel_w = w
        else:
            panel_w = (w - 12) // 2
            out.append(f'<rect x="{x + panel_w + 12}" y="{ty}" width="{panel_w}" height="170" rx="10" fill="{_PANEL}" stroke="{_BORDER}"/>')
            mvals = [("Availability", "99.2%", _EMERALD), ("Burn rate", "1.4x", _AMBER),
                     ("Budget", "62%", _SKY), ("Prediction", "Stable", _VIOLET)]
            for i, (lbl, val, col) in enumerate(mvals):
                my = ty + 18 + i * 38
                out.append(f'<text x="{x + panel_w + 26}" y="{my + 4}" fill="{_MUTED}" font-size="11">{lbl}</text>')
                out.append(f'<text x="{x + panel_w * 2 - 16}" y="{my + 4}" fill="{col}" font-size="13" font-weight="700" text-anchor="end">{val}</text>')
        out.append(f'<rect x="{x}" y="{ty}" width="{panel_w}" height="170" rx="10" fill="{_PANEL}" stroke="{_BORDER}"/>')
        for i in range(4):
            ry = ty + 20 + i * 36
            out.append(f'<rect x="{x + 14}" y="{ry}" width="10" height="10" rx="2" fill="{_VIOLET}"/>')
            out.append(f'<rect x="{x + 32}" y="{ry}" width="{panel_w - 110}" height="8" rx="4" fill="{_BORDER}"/>')
            out.append(f'<rect x="{x + panel_w - 70}" y="{ry}" width="54" height="8" rx="4" fill="{_PANEL2}"/>')
        return "".join(out)

    def _workflow(self, x: int, y: int, w: int, key: str, compact: bool) -> str:
        out = []
        steps = ["Detect", "Investigate", "Recommend", "Remediate"]
        if compact:
            for i, st in enumerate(steps):
                ny = y + i * 70
                out.append(f'<rect x="{x}" y="{ny}" width="{w}" height="54" rx="10" fill="{_PANEL}" stroke="{_BORDER}"/>')
                out.append(f'<circle cx="{x + 28}" cy="{ny + 27}" r="14" fill="{_VIOLET}" opacity="0.25"/>')
                out.append(f'<text x="{x + 28}" y="{ny + 32}" fill="{_VIOLET}" font-size="13" font-weight="700" text-anchor="middle">{i + 1}</text>')
                out.append(f'<text x="{x + 52}" y="{ny + 32}" fill="{_TEXT}" font-size="13" font-weight="600">{st}</text>')
                if i < len(steps) - 1:
                    out.append(f'<line x1="{x + 28}" y1="{ny + 54}" x2="{x + 28}" y2="{ny + 70}" stroke="{_BORDER}" stroke-width="2"/>')
            return "".join(out)
        gap = 18
        nw = (w - gap * (len(steps) - 1)) // len(steps)
        for i, st in enumerate(steps):
            nx = x + i * (nw + gap)
            out.append(f'<rect x="{nx}" y="{y}" width="{nw}" height="120" rx="12" fill="{_PANEL}" stroke="{_BORDER}"/>')
            out.append(f'<circle cx="{nx + nw // 2}" cy="{y + 42}" r="20" fill="{_VIOLET}" opacity="0.22"/>')
            out.append(f'<text x="{nx + nw // 2}" y="{y + 48}" fill="{_VIOLET}" font-size="18" font-weight="700" text-anchor="middle">{i + 1}</text>')
            out.append(f'<text x="{nx + nw // 2}" y="{y + 86}" fill="{_TEXT}" font-size="13" font-weight="600" text-anchor="middle">{st}</text>')
            out.append(f'<rect x="{nx + nw // 2 - 30}" y="{y + 98}" width="60" height="14" rx="7" fill="{_EMERALD}" opacity="0.18"/>')
            out.append(f'<text x="{nx + nw // 2}" y="{y + 108}" fill="{_EMERALD}" font-size="9" font-weight="700" text-anchor="middle">DONE</text>')
            if i < len(steps) - 1:
                ax = nx + nw
                out.append(f'<line x1="{ax}" y1="{y + 60}" x2="{ax + gap}" y2="{y + 60}" stroke="{_VIOLET}" stroke-width="2"/>')
                out.append(f'<polygon points="{ax + gap},{y + 60} {ax + gap - 6},{y + 56} {ax + gap - 6},{y + 64}" fill="{_VIOLET}"/>')
        return "".join(out)
