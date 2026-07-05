"""Sprint 46A - Reliability Maturity Score Engine.

Persisted, organization-wide maturity assessment across seven reliability
dimensions (monitoring, incident response, deployment, SLO, capacity, cost
optimization, on-call). Each ``ReliabilityAssessment`` stores an overall 0-100
score + maturity level + strengths/weaknesses/recommendations; each
``ReliabilityScoreCategory`` row stores one dimension's sub-score and the signals
it was derived from. Strictly read-only with respect to the rest of the platform.
"""

import enum

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class MaturityLevel(str, enum.Enum):
    BEGINNER = "BEGINNER"
    DEVELOPING = "DEVELOPING"
    MATURE = "MATURE"
    ADVANCED = "ADVANCED"
    ELITE = "ELITE"


class MaturityCategory(str, enum.Enum):
    MONITORING = "MONITORING"
    INCIDENT_RESPONSE = "INCIDENT_RESPONSE"
    DEPLOYMENT = "DEPLOYMENT"
    SLO = "SLO"
    CAPACITY = "CAPACITY"
    COST_OPTIMIZATION = "COST_OPTIMIZATION"
    ONCALL = "ONCALL"


class ReliabilityAssessment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "reliability_assessments"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    maturity_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MaturityLevel.BEGINNER.value
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths: Mapped[list | None] = mapped_column(JSON, nullable=True)
    weaknesses: Mapped[list | None] = mapped_column(JSON, nullable=True)
    recommendations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Snapshot of category scores + score deltas vs the previous assessment.
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ReliabilityScoreCategory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "reliability_score_categories"

    assessment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("reliability_assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    maturity_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MaturityLevel.BEGINNER.value
    )
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    signals: Mapped[dict | None] = mapped_column(JSON, nullable=True)
