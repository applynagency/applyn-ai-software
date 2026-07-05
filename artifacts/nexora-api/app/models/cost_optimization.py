"""Sprint 43B — Cost Optimization Intelligence.

Read-only, advisory cost analytics. A ``CostOptimizationAnalysis`` records the
output of mining existing capacity metrics (43A), service health (42C),
deployment history, and monitoring data into: current cost, estimated waste,
potential savings, an optimization score, idle/over-provisioning/rightsizing
recommendations, non-production scheduling opportunities, a cost forecast
(30/90/365-day), and cost-trend analysis.

Strictly advisory: it never scales, deletes, or modifies any resource. Every
analysis is org-scoped and audited. No secrets.
"""

import enum

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDMixin


class OptimizationLevel(str, enum.Enum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"
    CRITICAL_WASTE = "CRITICAL_WASTE"


class CostRecommendationKind(str, enum.Enum):
    IDLE_RESOURCE = "IDLE_RESOURCE"
    OVERPROVISIONED = "OVERPROVISIONED"
    NON_PROD_SCHEDULE = "NON_PROD_SCHEDULE"


class CostOptimizationAnalysis(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cost_optimization_analyses"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cluster: Mapped[str | None] = mapped_column(String(120), nullable=True)
    service: Mapped[str | None] = mapped_column(String(200), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(50), nullable=True)

    current_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_waste: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    potential_savings: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    optimized_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    annual_savings: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    savings_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    optimization_score: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    optimization_level: Mapped[str] = mapped_column(
        String(30), nullable=False, default=OptimizationLevel.EXCELLENT.value
    )

    forecast_30d: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    forecast_90d: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    forecast_365d: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    idle_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overprovisioned_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    nonprod_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
