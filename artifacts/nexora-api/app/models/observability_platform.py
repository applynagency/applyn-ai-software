"""Enterprise Observability Platform models (Sprint 65B)."""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class ObsIntegration(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "obs_integrations"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    signal: Mapped[str] = mapped_column(String(20), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    credential_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class ObsSavedSearch(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "obs_saved_searches"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    signal: Mapped[str] = mapped_column(String(20), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class ObsCorrelationTimeline(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "obs_correlation_timelines"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    timeline: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)


class ObsSLOEvaluation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "obs_slo_evaluations"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    service_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    slo_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    objective: Mapped[str] = mapped_column(String(30), nullable=False)
    target: Mapped[float] = mapped_column(Float, nullable=False)
    actual: Mapped[float] = mapped_column(Float, nullable=False)
    error_budget_remaining: Mapped[float | None] = mapped_column(Float, nullable=True)
    burn_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    compliant: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ObsAlertGroup(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "obs_alert_groups"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    alert_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="WARNING")
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    suppressed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
