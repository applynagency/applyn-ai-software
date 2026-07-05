"""Sprint 44C — Change Failure Prediction Engine.

Stores the result of a deterministic, rules-based prediction of how likely a
candidate deployment/change is to cause an incident. The prediction composes
existing read-only platform intelligence (41D deployment risk, 42C service
health/SLO, 42D deployment safety signals, 43A capacity, 43B cost, 40A incident
history, 40C change intelligence, 44B blast radius).

No machine learning — every score is explained by weighted, inspectable factors.
Strictly read-only: nothing here deploys, rolls back, or mutates infrastructure.
Org-scoped. No secrets are stored.
"""

import enum

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class FailureRiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ChangeFailurePrediction(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "change_failure_predictions"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    environment: Mapped[str | None] = mapped_column(String(60), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(60), nullable=True)
    version: Mapped[str | None] = mapped_column(String(120), nullable=True)

    failure_probability: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default=FailureRiskLevel.LOW.value
    )
    expected_blast_radius: Mapped[str] = mapped_column(String(20), nullable=False, default="LOW")
    expected_customer_impact: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Explainability: weighted factors + likely failure modes + mitigations.
    contributing_factors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    mitigation_steps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Full report (failure modes, blast detail, history snapshot) for the get view.
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
