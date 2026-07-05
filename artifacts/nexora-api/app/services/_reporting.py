"""Shared building blocks for the reporting engine.

The Executive Report service is the single, canonical reporting engine. This
module factors out the reusable surface it builds on: RBAC guards, the read-only
dashboard composition, the "normalize a cadence/period string" validation, and
the PDF / HTML / Markdown export switch (``build_export``).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NexoraException
from app.repositories.audit import AuditLogRepository
from app.services.document_export import render_html, render_pdf
from app.services.reliability_dashboard import ReliabilityDashboardService
from app.tenancy.permissions import can_read_ai_teams, can_write_ai_teams


def now_utc() -> datetime:
    return datetime.now(UTC)


def build_export(
    markdown: str,
    fmt: str | None,
    *,
    title: str,
    filename_prefix: str,
    tag: str,
) -> tuple[bytes, str, str]:
    """Render ``markdown`` to a downloadable artifact in the requested format.

    Returns ``(content, media_type, filename)``. Raises ``NexoraException`` for
    unsupported formats, matching the historical behaviour of both report
    services.
    """
    fmt = (fmt or "pdf").lower()
    if fmt == "pdf":
        return render_pdf(markdown), "application/pdf", f"{filename_prefix}-{tag}.pdf"
    if fmt == "html":
        return (
            render_html(title, markdown).encode("utf-8"),
            "text/html",
            f"{filename_prefix}-{tag}.html",
        )
    if fmt in ("markdown", "md"):
        return markdown.encode("utf-8"), "text/markdown", f"{filename_prefix}-{tag}.md"
    if fmt == "csv":
        import csv
        import io

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["section", "content"])
        for line in (markdown or "").splitlines():
            if line.startswith("#"):
                writer.writerow([line.lstrip("# ").strip(), ""])
            elif line.strip():
                writer.writerow(["", line.strip()])
        return buf.getvalue().encode("utf-8"), "text/csv", f"{filename_prefix}-{tag}.csv"
    raise NexoraException(
        "Unsupported export format. Use pdf, html, or markdown.", status_code=400
    )


class ReportingServiceBase:
    """Common RBAC, dashboard wiring and validation for report services."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit_repo = AuditLogRepository(session)
        self.report_repo = None  # set by subclasses
        self.dashboard = ReliabilityDashboardService(session)

    def _ensure_read(self, user, org_context) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    def _ensure_write(self, user, org_context) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_write_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    @staticmethod
    def _normalize_choice(
        value: str | None, *, default: str, allowed, error_message: str
    ) -> str:
        normalized = (value or default).upper()
        if normalized not in allowed:
            raise NexoraException(error_message, status_code=400)
        return normalized
