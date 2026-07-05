"""Sprint 56D.4 — PlaybookDocumentationService.

Produces enterprise-grade integration guide deliverables from the enriched
PLAYBOOKS: a complete Markdown manual per integration and PDF / HTML / Markdown
exports (dependency-free). A new customer can follow the manual to connect the
integration without contacting support. Read-only, deterministic, no DB.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import NotFoundError
from app.services.customer_success_content import PLAYBOOKS, get_playbook
from app.services.document_export import render_html, render_pdf


def _esc(text: object) -> str:
    return str(text).replace("|", "\\|")


class PlaybookDocumentationService:
    """Integration playbook manuals and exports."""

    def _bullets(self, lines: list[str], items: list[Any]) -> None:
        for it in items:
            lines.append(f"- {_esc(it)}")
        lines.append("")

    def _markdown(self, p: dict[str, Any]) -> str:
        lines: list[str] = []
        lines.append(f"# {p['name']} Integration Playbook")
        lines.append("")
        lines.append(_esc(p["overview"]))
        lines.append("")

        lines.append("## Architecture diagram")
        lines.append("")
        lines.append("```mermaid")
        lines.append(str(p.get("architecture_mermaid") or p.get("architecture_diagram", "")))
        lines.append("```")
        lines.append("")

        lines.append("## Business value")
        lines.append("")
        lines.append(_esc(p.get("business_value", "")))
        lines.append("")

        lines.append("## Use cases")
        lines.append("")
        self._bullets(lines, p.get("use_cases", []))

        lines.append("## Required permissions")
        lines.append("")
        self._bullets(lines, p.get("required_permissions", []))

        lines.append("## Credential setup")
        lines.append("")
        self._bullets(lines, p.get("credential_setup", []))

        lines.append("## Step-by-step configuration")
        lines.append("")
        for s in p.get("configuration_steps", []):
            lines.append(f"### Step {s['order']}: {_esc(s['title'])}")
            lines.append("")
            lines.append(f"- Action: {_esc(s['action'])}")
            lines.append(f"- Expected result: {_esc(s['expected'])}")
            lines.append(f"- Screenshot: `{_esc(s.get('screenshot_id', ''))}` (route `{_esc(s.get('route', ''))}`)")
            lines.append("")

        lines.append("## Validation steps")
        lines.append("")
        self._bullets(lines, p.get("validation_steps", []))

        lines.append("## Expected screens")
        lines.append("")
        self._bullets(lines, p.get("expected_screens", []))

        lines.append("## Expected outputs")
        lines.append("")
        self._bullets(lines, p.get("expected_outputs", []))

        lines.append("## Security considerations")
        lines.append("")
        self._bullets(lines, p.get("security_notes", []))

        lines.append("## Common errors")
        lines.append("")
        for e in p.get("common_errors", []):
            lines.append(f"- {_esc(e['error'])} -> {_esc(e['fix'])}")
        lines.append("")

        lines.append("## Troubleshooting")
        lines.append("")
        self._bullets(lines, p.get("troubleshooting", []))

        lines.append("## Best practices")
        lines.append("")
        self._bullets(lines, p.get("best_practices", []))

        lines.append("## Screenshots & visuals")
        lines.append("")
        for v in p.get("visuals", []):
            note = f" — annotations: {', '.join(v['annotations'])}" if v.get("annotations") else ""
            lines.append(f"- [{_esc(v['kind'])}] {_esc(v['caption'])}{_esc(note)}")
        lines.append("")

        lines.append("## FAQ")
        lines.append("")
        for f in p.get("faq", []):
            lines.append(f"### {_esc(f['question'])}")
            lines.append("")
            lines.append(_esc(f["answer"]))
            lines.append("")

        return "\n".join(lines)

    def manual(self, key: str) -> dict[str, Any]:
        p = get_playbook(key)
        if not p:
            raise NotFoundError("Integration playbook", key)
        return {
            "key": p["key"],
            "name": p["name"],
            "diagram": p.get("architecture_mermaid") or p.get("architecture_diagram", ""),
            "markdown": self._markdown(p),
        }

    def manuals(self) -> dict[str, Any]:
        items = [self.manual(p["key"]) for p in PLAYBOOKS]
        return {"items": items, "total": len(items)}

    def export(self, key: str, fmt: str) -> tuple[bytes | str, str, str]:
        p = get_playbook(key)
        if not p:
            raise NotFoundError("Integration playbook", key)
        markdown = self._markdown(p)
        title = f"{p['name']} Integration Playbook"
        fmt = (fmt or "pdf").lower()
        if fmt in ("markdown", "md"):
            return markdown, "text/markdown", f"playbook-{key}.md"
        if fmt == "html":
            return render_html(title, markdown), "text/html", f"playbook-{key}.html"
        return render_pdf(markdown), "application/pdf", f"playbook-{key}.pdf"
