"""Customer integration onboarding sessions (Sprint 67A)."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin

ONBOARDING_STATUSES = frozenset({
    "DRAFT",
    "CREDENTIALS_ADDED",
    "VALIDATING",
    "VALIDATED",
    "READY_FOR_PILOT",
    "FAILED",
    "REAUTH_REQUIRED",
    "CANCELLED",
})

ONBOARDING_PROVIDERS = frozenset({
    "KUBERNETES",
    "GITHUB",
    "GITHUB_ENTERPRISE",
    "GITEA",
    "PROMETHEUS",
})

ENV_CLASSIFICATIONS = frozenset({
    "development",
    "test",
    "qa",
    "uat",
    "staging",
    "production",
})


class IntegrationOnboardingSession(Base, UUIDMixin, TimestampMixin):
    """Persisted wizard state — separate from int_connection_registry until validated."""

    __tablename__ = "int_onboarding_sessions"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="DRAFT")
    environment_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    environment_classification: Mapped[str | None] = mapped_column(String(30), nullable=True)
    scope: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    intended_for_pilot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    owner_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    credential_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    validation_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_refs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    required_capabilities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    missing_capabilities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    readiness_verdict: Mapped[str | None] = mapped_column(String(30), nullable=True)
    registry_connection_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    acknowledged_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
