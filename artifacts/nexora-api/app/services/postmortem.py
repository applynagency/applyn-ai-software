"""Sprint 44A — AI Postmortem & Learning Engine.

Synthesizes an executive-grade postmortem from existing incident intelligence:

* 40A RCA / investigation (summary, root cause, confidence, suspected trigger)
* 40B timeline events
* 40C change-intelligence (triggering change)
* 41A recommendations
* 41B/41C remediation actions

It is generated automatically when an incident is resolved, can be regenerated
on demand, and exported (PDF / HTML / Markdown). It never mutates the incident
workflow — it only reads existing records and writes its own report. Org-scoped
and audited.
"""

from __future__ import annotations

from datetime import UTC

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NexoraException
from app.models.incident import RemediationActionStatus
from app.models.postmortem import PostmortemStatus
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.incident import (
    DeploymentChangeEventRepository,
    IncidentInvestigationRepository,
    IncidentRecommendationRepository,
    IncidentRemediationActionRepository,
    IncidentTimelineEventRepository,
)
from app.repositories.postmortem import PostmortemRepository
from app.schemas.postmortem import PostmortemResponse
from app.services.document_export import render_html, render_pdf
from app.tenancy.permissions import can_read_ai_teams, can_write_ai_teams

logger = structlog.get_logger(__name__)

_SECTION_FIELDS = (
    "title", "severity", "source", "confidence_score", "executive_summary",
    "impact_analysis", "timeline_summary", "root_cause", "triggering_change",
    "resolution", "lessons_learned", "action_items", "content_markdown",
)


def _fmt_ts(dt) -> str:
    if dt is None:
        return "unknown time"
    if isinstance(dt, str):
        return dt
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(dt)


class PostmortemService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.pm_repo = PostmortemRepository(session)
        self.inv_repo = IncidentInvestigationRepository(session)
        self.timeline_repo = IncidentTimelineEventRepository(session)
        self.change_repo = DeploymentChangeEventRepository(session)
        self.rec_repo = IncidentRecommendationRepository(session)
        self.action_repo = IncidentRemediationActionRepository(session)
        self.audit_repo = AuditLogRepository(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    # ------------------------------------------------------------- public API
    async def generate(self, user, org_context, investigation_id: str, *, force: bool = True) -> PostmortemResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        inv = await self.inv_repo.get_for_org(investigation_id, organization_id)
        if inv is None:
            raise NexoraException("Incident not found.", status_code=404)

        pm, created = await self._build_and_store(
            organization_id, inv, created_by=user.id, generated_by="MANUAL", force=force
        )
        await self.audit_repo.log(
            action="postmortem_generated" if created else "postmortem_regenerated",
            resource_type="incident_postmortem",
            resource_id=pm.id,
            user_id=user.id,
            details={
                "organization_id": organization_id,
                "incident_id": investigation_id,
                "version": pm.version,
            },
        )
        await self.session.commit()
        return self._to_response(pm)

    async def auto_generate_for_incident(
        self, organization_id: str, investigation_id: str, user_id: str | None
    ):
        """Best-effort auto-generation when an incident is resolved.

        Idempotent (skips if a postmortem already exists). Does NOT commit — the
        caller's transaction (the resolve flow) owns the commit. Never raises so
        the incident workflow is never affected.
        """
        try:
            inv = await self.inv_repo.get_for_org(investigation_id, organization_id)
            if inv is None:
                return None
            existing = await self.pm_repo.get_for_investigation(investigation_id, organization_id)
            if existing is not None:
                return existing
            pm, _ = await self._build_and_store(
                organization_id, inv, created_by=user_id, generated_by="AUTO", force=False
            )
            await self.audit_repo.log(
                action="postmortem_auto_generated",
                resource_type="incident_postmortem",
                resource_id=pm.id,
                user_id=user_id,
                details={"organization_id": organization_id, "incident_id": investigation_id},
            )
            return pm
        except Exception as exc:  # never break the resolve flow
            logger.warning("postmortem_auto_generation_failed", incident_id=investigation_id, error=str(exc))
            return None

    async def list(self, user, org_context, *, offset: int, limit: int):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        rows, total = await self.pm_repo.list_for_org(organization_id, offset=offset, limit=limit)
        return rows, total

    async def get(self, user, org_context, postmortem_id: str) -> PostmortemResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        pm = await self.pm_repo.get_for_org(postmortem_id, organization_id)
        if pm is None:
            raise NexoraException("Postmortem not found.", status_code=404)
        await self.audit_repo.log(
            action="postmortem_viewed",
            resource_type="incident_postmortem",
            resource_id=pm.id,
            user_id=user.id,
            details={"organization_id": organization_id},
        )
        await self.session.commit()
        return self._to_response(pm)

    async def update(self, user, org_context, postmortem_id: str, data) -> PostmortemResponse:
        """Sprint 58A.4 — apply human edits to a postmortem (editable report)."""
        organization_id = org_context.requires_organization
        if not user.is_superuser and (
            not org_context.role or not can_write_ai_teams(org_context.role)
        ):
            raise ForbiddenError()
        pm = await self.pm_repo.get_for_org(postmortem_id, organization_id)
        if pm is None:
            raise NexoraException("Postmortem not found.", status_code=404)

        fields: dict = {}
        for name in (
            "title", "executive_summary", "impact_analysis", "timeline_summary",
            "root_cause", "triggering_change", "resolution", "lessons_learned",
            "content_markdown",
        ):
            value = getattr(data, name, None)
            if value is not None:
                fields[name] = value
        if getattr(data, "action_items", None) is not None:
            fields["action_items"] = [
                item.model_dump() if hasattr(item, "model_dump") else dict(item)
                for item in data.action_items
            ]
        fields["status"] = PostmortemStatus.EDITED.value
        fields["generated_by"] = "MANUAL"
        fields["version"] = (pm.version or 1) + 1
        pm = await self.pm_repo.update(pm, **fields)
        await self.audit_repo.log(
            action="postmortem_edited",
            resource_type="incident_postmortem",
            resource_id=pm.id,
            user_id=user.id,
            details={"organization_id": organization_id, "version": pm.version},
        )
        await self.session.commit()
        return self._to_response(pm)

    async def export(self, user, org_context, postmortem_id: str, fmt: str) -> tuple[bytes, str, str]:
        """Return (content_bytes, media_type, filename)."""
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        pm = await self.pm_repo.get_for_org(postmortem_id, organization_id)
        if pm is None:
            raise NexoraException("Postmortem not found.", status_code=404)

        fmt = (fmt or "pdf").lower()
        markdown = pm.content_markdown or f"# {pm.title}\n\n(No content)"
        safe = (pm.investigation_id or pm.id)[:18]
        if fmt == "pdf":
            content = render_pdf(markdown)
            media_type, filename = "application/pdf", f"postmortem-{safe}.pdf"
        elif fmt in ("md", "markdown"):
            content = markdown.encode("utf-8")
            media_type, filename = "text/markdown; charset=utf-8", f"postmortem-{safe}.md"
        elif fmt == "html":
            content = render_html(pm.title, markdown).encode("utf-8")
            media_type, filename = "text/html; charset=utf-8", f"postmortem-{safe}.html"
        else:
            raise NexoraException("Unsupported export format. Use pdf, html, or markdown.", status_code=400)

        await self.audit_repo.log(
            action="postmortem_exported",
            resource_type="incident_postmortem",
            resource_id=pm.id,
            user_id=user.id,
            details={"organization_id": organization_id, "format": fmt},
        )
        await self.session.commit()
        return content, media_type, filename

    # --------------------------------------------------------------- internals
    async def _build_and_store(self, organization_id, inv, *, created_by, generated_by, force):
        existing = await self.pm_repo.get_for_investigation(inv.id, organization_id)
        if existing is not None and not force:
            return existing, False

        composed = await self._compose(organization_id, inv)

        if existing is not None:
            await self.pm_repo.update(
                existing,
                version=existing.version + 1,
                status=PostmortemStatus.REGENERATED.value,
                generated_by=generated_by,
                **composed,
            )
            return existing, False

        pm = await self.pm_repo.create(
            organization_id=organization_id,
            investigation_id=inv.id,
            status=PostmortemStatus.GENERATED.value,
            version=1,
            generated_by=generated_by,
            created_by=created_by,
            **composed,
        )
        return pm, True

    async def _compose(self, organization_id: str, inv) -> dict:
        timeline = await self.timeline_repo.list_for_investigation(inv.id, organization_id)
        changes = await self.change_repo.list_for_investigation(inv.id, organization_id)
        recommendations = await self.rec_repo.list_for_investigation(inv.id, organization_id)
        actions = await self.action_repo.list_for_investigation(inv.id, organization_id)

        severity = (inv.severity or "UNSPECIFIED").upper()
        source = (inv.source or "MANUAL").upper()
        title = f"Postmortem: {inv.title}"
        confidence = inv.confidence_score

        # --- Executive Summary ---
        sev_phrase = {
            "CRITICAL": "a critical-severity", "HIGH": "a high-severity",
            "WARNING": "a warning-level", "INFO": "an informational",
        }.get(severity, "an")
        opened = _fmt_ts(inv.created_at)
        exec_lines = [
            f"This report summarizes {sev_phrase} incident, \"{inv.title}\", "
            f"first investigated on {opened}.",
        ]
        if inv.summary:
            exec_lines.append(inv.summary.strip())
        else:
            exec_lines.append(
                "An automated investigation was performed across the connected "
                "observability and change sources."
            )
        if confidence is not None:
            exec_lines.append(f"Root-cause confidence: {confidence}%.")
        executive_summary = "\n\n".join(exec_lines)

        # --- Impact Analysis ---
        impacted_services = sorted({
            (e.event_metadata or {}).get("service")
            for e in timeline
            if isinstance(e.event_metadata, dict) and (e.event_metadata or {}).get("service")
        })
        impact_lines = [
            f"- Severity: {severity}",
            f"- Detection source: {source}",
            f"- Timeline events recorded: {len(timeline)}",
            f"- Correlated changes reviewed: {len(changes)}",
        ]
        if impacted_services:
            impact_lines.append(f"- Affected services: {', '.join(impacted_services)}")
        if inv.suspected_provider:
            impact_lines.append(f"- Primary signal provider: {inv.suspected_provider}")
        impact_analysis = "\n".join(impact_lines)

        # --- Timeline ---
        if timeline:
            tl_lines = [
                f"- {_fmt_ts(e.event_timestamp)} — [{e.provider or 'system'}] {e.title}"
                for e in timeline
            ]
            timeline_summary = "\n".join(tl_lines)
        else:
            timeline_summary = "No timeline events were recorded for this incident."

        # --- Root Cause ---
        root_cause = (inv.root_cause or "").strip() or (
            "A definitive root cause was not established by the automated "
            "investigation. Manual review is recommended."
        )

        # --- Triggering Change ---
        triggering_change = self._triggering_change(inv, changes)

        # --- Resolution ---
        resolution = self._resolution(actions, recommendations)

        # --- Action Items ---
        action_items = self._action_items(recommendations, actions)

        # --- Lessons Learned ---
        lessons_learned = self._lessons_learned(inv, timeline, changes, recommendations, confidence)

        content_markdown = self._render_markdown(
            title=title, severity=severity, source=source, confidence=confidence,
            opened=opened, executive_summary=executive_summary, impact_analysis=impact_analysis,
            timeline_summary=timeline_summary, root_cause=root_cause,
            triggering_change=triggering_change, resolution=resolution,
            action_items=action_items, lessons_learned=lessons_learned,
        )

        return {
            "title": title,
            "severity": severity,
            "source": source,
            "confidence_score": confidence,
            "executive_summary": executive_summary,
            "impact_analysis": impact_analysis,
            "timeline_summary": timeline_summary,
            "root_cause": root_cause,
            "triggering_change": triggering_change,
            "resolution": resolution,
            "lessons_learned": lessons_learned,
            "action_items": action_items,
            "content_markdown": content_markdown,
        }

    @staticmethod
    def _triggering_change(inv, changes) -> str:
        if inv.suspected_trigger:
            prov = f" (provider: {inv.suspected_provider})" if inv.suspected_provider else ""
            return f"{inv.suspected_trigger.strip()}{prov}"
        if changes:
            c = changes[-1]
            ver = f" version {c.version}" if getattr(c, "version", None) else ""
            actor = f" by {c.actor}" if getattr(c, "actor", None) else ""
            return (
                f"Closest preceding change: [{c.provider or 'unknown'}] {c.change_type} — "
                f"{c.title}{ver}{actor} at {_fmt_ts(c.change_timestamp)}."
            )
        return "No specific triggering change was correlated to this incident."

    @staticmethod
    def _resolution(actions, recommendations) -> str:
        completed = [a for a in actions if a.status == RemediationActionStatus.COMPLETED.value]
        if completed:
            lines = ["The incident was remediated via the following completed action(s):"]
            for a in completed:
                lines.append(f"- {a.title} ({a.action_type}) at {_fmt_ts(a.executed_at)}")
            return "\n".join(lines)
        if recommendations:
            return (
                "The incident was resolved through on-call response. Recommended "
                "remediations were generated and tracked as action items (see below)."
            )
        return (
            "The incident was resolved through on-call response. No automated "
            "remediation actions were executed."
        )

    @staticmethod
    def _action_items(recommendations, actions) -> list[dict]:
        items: list[dict] = []
        for r in recommendations:
            items.append({
                "title": r.title,
                "detail": (r.description or "").strip() or None,
                "owner": "Owning team / on-call",
                "status": "OPEN",
                "source": "recommendation",
                "risk_level": getattr(r, "risk_level", None),
            })
        for a in actions:
            items.append({
                "title": a.title,
                "detail": (getattr(a, "description", None) or "").strip() or None,
                "owner": "Owning team / on-call",
                "status": a.status,
                "source": "remediation_action",
                "risk_level": getattr(a, "risk_level", None),
            })
        if not items:
            items.append({
                "title": "Conduct a manual review of this incident",
                "detail": "No automated recommendations were generated; review signals and document findings.",
                "owner": "Owning team / on-call",
                "status": "OPEN",
                "source": "default",
                "risk_level": None,
            })
        return items

    @staticmethod
    def _lessons_learned(inv, timeline, changes, recommendations, confidence) -> str:
        lessons: list[str] = []
        if changes:
            lessons.append(
                "A change was correlated to this incident — strengthen pre-deployment "
                "checks and canary rollout for the affected service."
            )
        if confidence is not None and confidence < 60:
            lessons.append(
                "Root-cause confidence was low — improve observability coverage and "
                "structured logging to speed future diagnosis."
            )
        if not timeline:
            lessons.append(
                "No timeline signals were available — ensure monitoring providers are "
                "connected so future incidents build an automatic timeline."
            )
        if recommendations:
            lessons.append(
                "Actionable remediations were available automatically — codify these into "
                "runbooks to reduce time-to-mitigation."
            )
        if not lessons:
            lessons.append(
                "Review detection and response timing to identify opportunities to reduce "
                "time-to-detect and time-to-resolve."
            )
        return "\n".join(f"- {lesson}" for lesson in lessons)

    @staticmethod
    def _render_markdown(*, title, severity, source, confidence, opened, executive_summary,
                         impact_analysis, timeline_summary, root_cause, triggering_change,
                         resolution, action_items, lessons_learned) -> str:
        conf = f"{confidence}%" if confidence is not None else "n/a"
        ai_lines = []
        for i, a in enumerate(action_items, 1):
            risk = f" [{a['risk_level']}]" if a.get("risk_level") else ""
            status = f" ({a['status']})" if a.get("status") else ""
            ai_lines.append(f"- {i}. {a['title']}{risk}{status}")
            if a.get("detail"):
                ai_lines.append(f"  - {a['detail']}")
        parts = [
            f"# {title}",
            "",
            f"**Severity:** {severity}  |  **Source:** {source}  |  "
            f"**Root-cause confidence:** {conf}  |  **First investigated:** {opened}",
            "",
            "## Executive Summary",
            executive_summary,
            "",
            "## Impact Analysis",
            impact_analysis,
            "",
            "## Timeline",
            timeline_summary,
            "",
            "## Root Cause",
            root_cause,
            "",
            "## Triggering Change",
            triggering_change,
            "",
            "## Resolution",
            resolution,
            "",
            "## Action Items",
            "\n".join(ai_lines),
            "",
            "## Lessons Learned",
            lessons_learned,
            "",
            "---",
            "_Generated automatically by the AI Postmortem & Learning Engine. "
            "This report is advisory and does not modify the incident workflow._",
        ]
        return "\n".join(parts)

    @staticmethod
    def _to_response(pm) -> PostmortemResponse:
        return PostmortemResponse.model_validate(pm)
