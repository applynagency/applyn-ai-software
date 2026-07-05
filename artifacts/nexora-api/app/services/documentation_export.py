"""Sprint 56B — DocumentationExportService.

Renders a visual documentation pack (PDF / HTML / Markdown) that includes
embedded screenshot references, annotations, architecture diagrams, and
navigation maps. Reuses the dependency-free ``document_export`` renderer.
"""

from __future__ import annotations

from app.services.architecture_diagrams import ArchitectureDiagramService
from app.services.customer_success_content import MODULES
from app.services.document_export import render_html, render_pdf
from app.services.screenshot_annotation import ScreenshotAnnotationService
from app.services.visual_documentation import VisualDocumentationService

_TITLE = "Nexora Visual Documentation Pack"


def _md_escape(text: str) -> str:
    return str(text).replace("|", "\\|")


class DocumentationExportService:
    def __init__(self) -> None:
        self.visual = VisualDocumentationService()
        self.annotation = ScreenshotAnnotationService()
        self.architecture = ArchitectureDiagramService()

    def _markdown(self) -> str:
        lines: list[str] = [f"# {_TITLE}", ""]

        lines.append("## Module Guides (with embedded screenshots)")
        lines.append("")
        for m in MODULES:
            lines.append(f"### {m['name']}")
            lines.append("")
            lines.append("Architecture diagram (Mermaid):")
            lines.append("")
            lines.append("```mermaid")
            lines.append(str(m.get("architecture_diagram", "")))
            lines.append("```")
            lines.append("")
            for s in m["steps"]:
                lines.append(f"- Step {s['order']}: {_md_escape(s['action'])}")
                lines.append(f"  - Screenshot: `{s.get('screenshot_id', '')}`")
                lines.append(f"  - Caption: {_md_escape(s.get('caption', ''))}")
                lines.append(f"  - Alt text: {_md_escape(s.get('alt_text', ''))}")
                lines.append(f"  - Expected result: {_md_escape(s['expected'])}")
                anns = self.annotation.list(screenshot_id=s.get("screenshot_id", ""))
                if anns:
                    targets = ", ".join(a["target"] for a in anns)
                    lines.append(f"  - Annotations: {_md_escape(targets)}")
            lines.append("")

        lines.append("## Navigation Maps")
        lines.append("")
        for nm in self.visual.navigation_maps()["items"]:
            lines.append(f"### {nm['name']}")
            lines.append(f"{nm['flow']}")
            lines.append("")

        lines.append("## Architecture Diagrams")
        lines.append("")
        for d in self.architecture.list()["items"]:
            lines.append(f"### {d['name']}")
            lines.append("```mermaid")
            lines.append(str(d["mermaid"]))
            lines.append("```")
            lines.append("")

        return "\n".join(lines)

    def export(self, fmt: str) -> tuple[bytes | str, str, str]:
        fmt = (fmt or "pdf").lower()
        markdown = self._markdown()
        if fmt == "markdown" or fmt == "md":
            return markdown, "text/markdown", "nexora-visual-docs.md"
        if fmt == "html":
            return render_html(_TITLE, markdown), "text/html", "nexora-visual-docs.html"
        # default: pdf
        return render_pdf(markdown), "application/pdf", "nexora-visual-docs.pdf"
