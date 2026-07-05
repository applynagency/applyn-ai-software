"""Sprint 56D.3 — JourneyDocumentationService.

Produces end-to-end customer journey deliverables from the enriched JOURNEYS:

* diagrams   — the Mermaid diagram per journey
* manual     — a complete, step-by-step Markdown manual for a journey
* export     — the manual rendered as PDF / HTML / Markdown (dependency-free)

A customer can follow the manual and complete the journey without assistance.
Read-only, deterministic, no DB.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import NotFoundError
from app.services.customer_success_content import JOURNEYS, get_journey
from app.services.document_export import render_html, render_pdf


def _md_escape(text: object) -> str:
    return str(text).replace("|", "\\|")


class JourneyDocumentationService:
    """End-to-end journey diagrams, manuals, and exports."""

    # -- diagrams ---------------------------------------------------------- #
    def diagrams(self) -> dict[str, Any]:
        items = [
            {"key": j["key"], "name": j["name"], "diagram": j.get("diagram", "")}
            for j in JOURNEYS
        ]
        return {"items": items, "total": len(items)}

    # -- manuals ----------------------------------------------------------- #
    def _journey_markdown(self, journey: dict[str, Any]) -> str:
        lines: list[str] = []
        lines.append(f"# {journey['name']} — Customer Journey Manual")
        lines.append("")
        lines.append(_md_escape(journey["summary"]))
        lines.append("")
        lines.append("## Journey diagram (Mermaid)")
        lines.append("")
        lines.append("```mermaid")
        lines.append(str(journey.get("diagram", "")))
        lines.append("```")
        lines.append("")
        lines.append("## Expected outcomes")
        lines.append("")
        for o in journey.get("expected_outcomes", []):
            lines.append(f"- {_md_escape(o)}")
        lines.append("")
        lines.append("## Step-by-step walkthrough")
        lines.append("")
        for s in journey["stages"]:
            lines.append(f"### Step {s['order']}: {_md_escape(s['title'])}")
            lines.append("")
            lines.append(_md_escape(s.get("description", "")))
            lines.append("")
            nav = " > ".join(str(n) for n in s.get("navigation", [])) or "—"
            lines.append(f"- Navigation: {_md_escape(nav)}")
            lines.append(f"- Screenshot: `{_md_escape(s.get('screenshot', ''))}` (route `{_md_escape(s.get('route', ''))}`)")
            screens = ", ".join(str(x) for x in s.get("expected_screen", [])) or "—"
            lines.append(f"- Expected screen: {_md_escape(screens)}")
            lines.append(f"- What happens internally: {_md_escape(s.get('internal', ''))}")
            lines.append(f"- Expected outcome: {_md_escape(s.get('expected_outcome', ''))}")
            issues = s.get("common_issues", [])
            recoveries = s.get("recovery_steps", [])
            if issues:
                lines.append("- Common issues:")
                for it in issues:
                    lines.append(f"  - {_md_escape(it)}")
            if recoveries:
                lines.append("- Recovery steps:")
                for rc in recoveries:
                    lines.append(f"  - {_md_escape(rc)}")
            lines.append("")
        return "\n".join(lines)

    def manual(self, key: str) -> dict[str, Any]:
        journey = get_journey(key)
        if not journey:
            raise NotFoundError("Journey guide", key)
        return {
            "key": journey["key"],
            "name": journey["name"],
            "diagram": journey.get("diagram", ""),
            "markdown": self._journey_markdown(journey),
        }

    def manuals(self) -> dict[str, Any]:
        items = [self.manual(j["key"]) for j in JOURNEYS]
        return {"items": items, "total": len(items)}

    # -- export ------------------------------------------------------------ #
    def export(self, key: str, fmt: str) -> tuple[bytes | str, str, str]:
        journey = get_journey(key)
        if not journey:
            raise NotFoundError("Journey guide", key)
        markdown = self._journey_markdown(journey)
        title = f"{journey['name']} — Customer Journey Manual"
        fmt = (fmt or "pdf").lower()
        if fmt in ("markdown", "md"):
            return markdown, "text/markdown", f"journey-{key}.md"
        if fmt == "html":
            return render_html(title, markdown), "text/html", f"journey-{key}.html"
        return render_pdf(markdown), "application/pdf", f"journey-{key}.pdf"
