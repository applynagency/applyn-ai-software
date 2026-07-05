"""Sprint 44A — AI Postmortem & Learning Engine.

An ``IncidentPostmortem`` is an executive-grade report synthesized from the
existing incident intelligence (40A RCA, 40B timeline, 40C change intelligence,
41A recommendations, 41B/41C remediation actions). It is generated automatically
when an incident is resolved, can be regenerated on demand, and exported.

Read-only with respect to the incident workflow: generating or regenerating a
postmortem never changes the underlying investigation, timeline, recommendations,
or remediation actions. Org-scoped and audited.
"""

import enum

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDMixin


class PostmortemStatus(str, enum.Enum):
    GENERATED = "GENERATED"
    REGENERATED = "REGENERATED"
    EDITED = "EDITED"


class IncidentPostmortem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "incident_postmortems"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # One postmortem per incident; regeneration updates in place.
    investigation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("incident_investigations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PostmortemStatus.GENERATED.value
    )
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confidence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    generated_by: Mapped[str] = mapped_column(String(20), nullable=False, default="AUTO")

    # Narrative sections (Markdown).
    executive_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeline_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggering_change: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    lessons_learned: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Structured action items: [{title, detail, owner, status, source, risk_level}]
    action_items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Fully rendered Markdown document (used for export).
    content_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
