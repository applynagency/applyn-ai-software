"""Sprint 42D — Safe Deployment Intelligence (Canary & Pre-Deployment Risk Guard).

Advisory, read-only analytics. A ``DeploymentSafetyAnalysis`` records the output
of composing the Sprint 41D deployment-risk score with Sprint 42C SLO health,
recent incidents, rollbacks, and open remediation actions into a safety score,
readiness state, blast-radius estimate, canary recommendation, deployment-window
guidance, and guardrail warnings.

Strictly advisory: it never executes, blocks, rolls back, or mutates a
deployment. Every analysis is org-scoped and audited. No secrets stored.
"""

import enum

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDMixin


class ReadinessState(str, enum.Enum):
    READY = "READY"
    AT_RISK = "AT_RISK"
    NOT_READY = "NOT_READY"


class BlastRadiusLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CanaryStrategy(str, enum.Enum):
    FULL_ROLLOUT = "FULL_ROLLOUT"
    CANARY_5 = "CANARY_5"
    CANARY_10 = "CANARY_10"
    CANARY_25 = "CANARY_25"
    BLUE_GREEN = "BLUE_GREEN"


class DeploymentSafetyAnalysis(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "deployment_safety_analyses"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    environment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)

    safety_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    readiness: Mapped[str] = mapped_column(String(20), nullable=False, default=ReadinessState.READY.value)
    blast_radius: Mapped[str] = mapped_column(String(20), nullable=False, default=BlastRadiusLevel.LOW.value)
    recommended_strategy: Mapped[str] = mapped_column(
        String(30), nullable=False, default=CanaryStrategy.FULL_ROLLOUT.value
    )
    recommended_window: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
