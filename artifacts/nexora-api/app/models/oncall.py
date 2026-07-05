"""Sprint 42B — Intelligent On-Call & Escalation Engine.

Additive, customer-facing models that let the platform answer "who owns this
incident, who is on-call, who should approve, and who should be paged" — and to
escalate automatically when nobody acknowledges in time.

Strictly orchestration metadata: ownership maps, rotation schedules, escalation
policies, the per-incident assignment, and an escalation audit trail. No secrets
are stored; remediation still requires explicit human approval (Sprint 41B/C).
"""

import enum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDMixin


class OnCallRotationType(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


class IncidentAssignmentState(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"


class EscalationTargetType(str, enum.Enum):
    ONCALL = "ONCALL"
    PRIMARY_OWNER = "PRIMARY_OWNER"
    SECONDARY_OWNER = "SECONDARY_OWNER"
    TEAM_LEAD = "TEAM_LEAD"
    MANAGEMENT = "MANAGEMENT"
    USER = "USER"


class ServiceOwner(Base, UUIDMixin, TimestampMixin):
    """Maps a service to its owners and escalation group (org-scoped)."""

    __tablename__ = "service_owners"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    primary_owner_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    secondary_owner_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    team: Mapped[str | None] = mapped_column(String(120), nullable=True)
    escalation_group: Mapped[str | None] = mapped_column(String(120), nullable=True)


class OnCallSchedule(Base, UUIDMixin, TimestampMixin):
    """A timezone-aware on-call rotation (daily/weekly) over an ordered list of
    participant user ids."""

    __tablename__ = "oncall_schedules"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    team: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    rotation_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OnCallRotationType.WEEKLY.value
    )
    timezone: Mapped[str] = mapped_column(String(60), nullable=False, default="UTC")
    # Ordered list of participant user ids (customer-safe; not secrets).
    participants: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Rotation anchor — the moment participant[0] starts their shift.
    anchor_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EscalationPolicy(Base, UUIDMixin, TimestampMixin):
    """A configurable, ordered escalation ladder. ``service_name`` NULL = the
    organization default policy applied when no service-specific policy exists."""

    __tablename__ = "escalation_policies"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    service_name: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EscalationStep(Base, UUIDMixin, TimestampMixin):
    """One rung of an escalation ladder: after N minutes, notify a target."""

    __tablename__ = "escalation_steps"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    policy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("escalation_policies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    after_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default=EscalationTargetType.ONCALL.value
    )
    # Explicit target user (for TEAM_LEAD / MANAGEMENT / USER targets).
    target_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    channels: Mapped[str] = mapped_column(String(40), nullable=False, default="slack,email")


class IncidentAssignment(Base, UUIDMixin, TimestampMixin):
    """The on-call ownership + acknowledgement state for a single incident."""

    __tablename__ = "incident_assignments"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("incident_investigations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    service_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    owner_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    responder_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approver_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    oncall_schedule_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("oncall_schedules.id", ondelete="SET NULL"), nullable=True
    )
    escalation_policy_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("escalation_policies.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=IncidentAssignmentState.OPEN.value
    )
    current_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assigned_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EscalationEvent(Base, UUIDMixin, TimestampMixin):
    """An audit record of one escalation notification fired for an incident."""

    __tablename__ = "escalation_events"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("incident_investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("incident_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    after_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    channels: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notified_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
