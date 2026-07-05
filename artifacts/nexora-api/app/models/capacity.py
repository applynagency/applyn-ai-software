"""Sprint 43A — Capacity Planning & Forecasting.

Read-only, rules-based capacity intelligence. ``CapacityMetric`` persists
normalized utilization samples (CPU / memory / storage / network and Kubernetes
node / pod metrics) ingested from existing monitoring sources. ``CapacityForecast``
stores a deterministic projection (7/30/90-day), saturation/exhaustion prediction,
an advisory scaling recommendation, and a cost-impact estimate.

Strictly advisory: it never scales, provisions, or mutates infrastructure. Every
forecast is org-scoped and audited. No secrets.
"""

import enum

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDMixin


class ResourceType(str, enum.Enum):
    CPU = "CPU"
    MEMORY = "MEMORY"
    STORAGE = "STORAGE"
    NETWORK = "NETWORK"
    NODE = "NODE"
    POD = "POD"
    # Sprint 43B — additional billable resources for cost optimization.
    VM = "VM"
    LOAD_BALANCER = "LOAD_BALANCER"
    DATABASE = "DATABASE"


class CapacityTrend(str, enum.Enum):
    GROWING = "GROWING"
    STABLE = "STABLE"
    DECLINING = "DECLINING"


class CapacityStatus(str, enum.Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ScalingAction(str, enum.Enum):
    NONE = "NONE"
    ADD_NODES = "ADD_NODES"
    INCREASE_MEMORY = "INCREASE_MEMORY"
    INCREASE_STORAGE = "INCREASE_STORAGE"
    INCREASE_REPLICAS = "INCREASE_REPLICAS"
    SCALE_CLUSTER = "SCALE_CLUSTER"


class CapacityMetric(Base, UUIDMixin, TimestampMixin):
    """A single normalized utilization sample for a resource in a scope."""

    __tablename__ = "capacity_metrics"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cluster: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    service: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    environment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    usage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    capacity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recorded_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class CapacityForecast(Base, UUIDMixin, TimestampMixin):
    """A deterministic capacity projection + advisory recommendation."""

    __tablename__ = "capacity_forecasts"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cluster: Mapped[str | None] = mapped_column(String(120), nullable=True)
    service: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    environment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_type: Mapped[str] = mapped_column(String(20), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)

    current_usage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    capacity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_utilization: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    growth_rate_per_day: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trend: Mapped[str] = mapped_column(String(20), nullable=False, default=CapacityTrend.STABLE.value)

    forecast_7d: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    forecast_30d: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    forecast_90d: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    saturation_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=90.0)
    saturation_date: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exhaustion_date: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=CapacityStatus.HEALTHY.value)

    recommendation_action: Mapped[str] = mapped_column(
        String(30), nullable=False, default=ScalingAction.NONE.value
    )
    recommendation: Mapped[str | None] = mapped_column(String(500), nullable=True)

    current_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    projected_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    delta_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    data_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
