"""Sprint 42C — Service Health & SLO Intelligence.

Additive, strictly read-only analytics models: a service catalog and SLO
definitions. The reliability math (availability, error budgets, burn rates,
violation prediction, incident correlation) is computed on demand by the service
layer from existing read-only data (monitoring alerts, incidents, on-call
assignments) — nothing here ever mutates or acts on infrastructure. No secrets.
"""

import enum

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDMixin


class ServiceTier(str, enum.Enum):
    TIER_1 = "TIER_1"  # business critical
    TIER_2 = "TIER_2"  # important
    TIER_3 = "TIER_3"  # best effort


class SLOType(str, enum.Enum):
    AVAILABILITY = "AVAILABILITY"
    LATENCY = "LATENCY"
    ERROR_RATE = "ERROR_RATE"


class LatencyPercentile(str, enum.Enum):
    P50 = "P50"
    P95 = "P95"
    P99 = "P99"


class Service(Base, UUIDMixin, TimestampMixin):
    """A catalogued service whose reliability is tracked against SLOs."""

    __tablename__ = "services"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # ``name`` is also the matching key for monitoring alerts / incident
    # assignments whose ``service`` field equals it.
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_team: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default=ServiceTier.TIER_2.value)


class ServiceSLO(Base, UUIDMixin, TimestampMixin):
    """A Service Level Objective: a reliability target over a rolling window."""

    __tablename__ = "service_slos"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slo_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SLOType.AVAILABILITY.value
    )
    target_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=99.9)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    # Latency-only: which percentile and the threshold it must stay under (ms).
    latency_percentile: Mapped[str | None] = mapped_column(String(10), nullable=True)
    threshold_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
