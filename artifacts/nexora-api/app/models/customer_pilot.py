"""Customer pilot portal models (Sprint 67B/67C)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin

CLOSEOUT_STATUSES = frozenset({
    "PENDING_OPERATOR_REVIEW",
    "CLOSED",
    "BLOCKED",
})

COMMUNICATION_CATEGORIES = frozenset({
    "PILOT_STATUS_UPDATE",
    "APPROVAL_REQUEST",
    "APPROVAL_REMINDER",
    "EXECUTION_UPDATE",
    "VERIFICATION_UPDATE",
    "EVIDENCE_READY",
    "CLOSEOUT_UPDATE",
})

COMMUNICATION_STATUSES = frozenset({"DRAFT", "SENT", "CANCELLED"})

REMINDER_TYPES = frozenset({"24H", "1H", "EXPIRED"})


class PilotApprovalPackage(Base, UUIDMixin, TimestampMixin):
    """Immutable approval package snapshot at proposal/approval time."""

    __tablename__ = "pilot_approval_packages"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    operation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    approval_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    rollback_plan_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    package: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    environment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class PilotCloseoutRequest(Base, UUIDMixin, TimestampMixin):
    """Customer-initiated closeout review — does not advance COMPLETE."""

    __tablename__ = "pilot_closeout_requests"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    enrollment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_OPERATOR_REVIEW")
    outcome_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    customer_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    signoff_contact: Mapped[str] = mapped_column(String(255), nullable=False)
    follow_up_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blockers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    requested_by: Mapped[str] = mapped_column(String(36), nullable=False)
    reviewed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class PilotCustomerCommunication(Base, UUIDMixin, TimestampMixin):
    """Customer-safe pilot communication (operator-authored or system-generated)."""

    __tablename__ = "pilot_customer_communications"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    enrollment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    operation_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    template_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    deep_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    recipient_user_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledgements: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class PilotCommunicationComment(Base, UUIDMixin, TimestampMixin):
    """Plain-text customer comment on a pilot communication."""

    __tablename__ = "pilot_communication_comments"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    communication_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)


class PilotNotificationPreference(Base, UUIDMixin, TimestampMixin):
    """Per-user customer pilot notification preferences."""

    __tablename__ = "pilot_notification_preferences"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_pilot_notification_prefs_org_user"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_reminders_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    evidence_ready_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    closeout_notifications_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")


class PilotApprovalReminderDelivery(Base, UUIDMixin, TimestampMixin):
    """Durable dedupe for approval reminder deliveries."""

    __tablename__ = "pilot_approval_reminder_deliveries"
    __table_args__ = (
        UniqueConstraint("approval_id", "reminder_type", name="uq_pilot_approval_reminder_type"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    approval_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    reminder_type: Mapped[str] = mapped_column(String(20), nullable=False)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


DELIVERY_STATUSES = frozenset({
    "queued", "sent", "delivered", "failed", "retrying", "cancelled", "suppressed_by_preference",
})


class PilotNotificationDelivery(Base, UUIDMixin, TimestampMixin):
    """Durable customer-pilot notification delivery tracking (Sprint 67D)."""

    __tablename__ = "pilot_notification_deliveries"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_pilot_notification_delivery_idem"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    communication_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    approval_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    recipient_user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class PilotSchedulerHealthSnapshot(Base, UUIDMixin, TimestampMixin):
    """Last-known scheduler/cron health for pilot background jobs."""

    __tablename__ = "pilot_scheduler_health_snapshots"

    job_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
