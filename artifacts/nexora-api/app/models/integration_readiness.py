"""Cross-platform integration readiness models (Sprint 65G)."""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin

LIFECYCLE_STATES = frozenset({
    "DRAFT", "VALIDATING", "CONNECTED", "DEGRADED", "FAILED",
    "DISCONNECTED", "EXPIRED", "REAUTH_REQUIRED",
})


class IntConnectionRegistry(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "int_connection_registry"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_int_registry_idempotency"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False)
    credential_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lifecycle_state: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True)
    provider_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="unavailable")
    capabilities: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    health_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_validated_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reauth_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class IntHealthHistory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "int_health_history"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    registry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("int_connection_registry.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    previous_state: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_state: Mapped[str] = mapped_column(String(30), nullable=False)
    probe_result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class IntExpiryReminder(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "int_expiry_reminder"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    registry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("int_connection_registry.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    expires_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    warning_level: Mapped[str] = mapped_column(String(10), nullable=False, default="30d")
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    snoozed_until: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_metadata: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)


class IntLiveEvidence(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "int_live_evidence"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    registry_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    operation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    operation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    verification: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
