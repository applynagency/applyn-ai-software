"""DevOps & SRE daily operations workspace models (Sprint 63C)."""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class WorkspaceMaintenanceWindow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ws_maintenance_windows"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="WINDOW")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="SCHEDULED")
    starts_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    impact_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    cluster_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    environment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class WorkspaceDailyBriefing(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ws_daily_briefings"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    briefing_date: Mapped[str] = mapped_column(String(10), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    sections: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    recommended_actions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    generated_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class WorkspaceShiftHandover(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ws_shift_handovers"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    sections: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    generated_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class WorkspaceAutomationSuggestion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ws_automation_suggestions"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class WorkspaceCalendarEvent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ws_calendar_events"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    starts_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reference_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
