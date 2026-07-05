"""Enterprise Incident Response & On-Call Platform models (Sprint 65C)."""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class IrScheduleOverride(Base, UUIDMixin, TimestampMixin):
    """Vacation / temporary on-call replacement."""

    __tablename__ = "ir_schedule_overrides"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    schedule_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("oncall_schedules.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    replacement_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    starts_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class IrStatusPage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ir_status_pages"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="PUBLIC")
    branding: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class IrStatusComponent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ir_status_components"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ir_status_pages.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OPERATIONAL")
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class IrStatusIncident(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ir_status_incidents"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ir_status_pages.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    incident_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="INVESTIGATING")
    impact: Mapped[str | None] = mapped_column(String(30), nullable=True)
    started_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updates: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class IrStatusSubscriber(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ir_status_subscribers"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    page_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ir_status_pages.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class IrCommunicationTemplate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ir_communication_templates"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class IrCommunication(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ir_communications"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    incident_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    scheduled_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class IrMajorIncident(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ir_major_incidents"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    incident_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    war_room_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    roles: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    stakeholders: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    decision_log: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    executive_bridge: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    started_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class IrCoordinatorRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ir_coordinator_runs"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    incident_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
