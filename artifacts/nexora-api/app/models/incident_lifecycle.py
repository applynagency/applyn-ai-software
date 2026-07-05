"""Sprint 58A.4 — Complete Incident Lifecycle.

Additive models that turn the incident detail page into a command center:

* ``IncidentLifecycleEvent`` — an append-only audit of *every* lifecycle action
  (state change, assignment, escalation, comment, task, remediation, war-room
  launch, postmortem). Powers the unified incident timeline.
* ``IncidentComment`` — human discussion / collaboration thread.
* ``IncidentTask`` — follow-up tasks tracked on the incident.

Customer-safe text only; never secrets. All org-scoped.
"""

import enum

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class IncidentLifecycleEventType(str, enum.Enum):
    STATE_CHANGE = "STATE_CHANGE"
    ASSIGNMENT = "ASSIGNMENT"
    ESCALATION = "ESCALATION"
    COMMENT = "COMMENT"
    TASK = "TASK"
    REMEDIATION = "REMEDIATION"
    WAR_ROOM = "WAR_ROOM"
    POSTMORTEM = "POSTMORTEM"
    NOTE = "NOTE"


class IncidentTaskStatus(str, enum.Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class IncidentLifecycleEvent(Base, UUIDMixin, TimestampMixin):
    """An append-only record of one action taken during an incident's lifecycle."""

    __tablename__ = "incident_lifecycle_events"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("incident_investigations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


class IncidentComment(Base, UUIDMixin, TimestampMixin):
    """Human collaboration / discussion on an incident."""

    __tablename__ = "incident_comments"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("incident_investigations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    author_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)


class IncidentTask(Base, UUIDMixin, TimestampMixin):
    """A follow-up task tracked on an incident."""

    __tablename__ = "incident_tasks"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("incident_investigations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=IncidentTaskStatus.TODO.value, server_default="TODO"
    )
    assignee_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
