"""Sprint 47C - Guided Setup Wizard.

A single ``onboarding_sessions`` row tracks a customer's progress through the
10-step onboarding wizard (org setup -> connect infra/monitoring/source control
-> run discovery -> generate catalog/dependency-graph/reliability+risk reports
-> finish). State is persisted so a customer can resume later.

Read-only orchestration: the wizard reports progress and recommendations by
inspecting existing platform data; it never mutates infrastructure. No secrets.
"""

import enum

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class OnboardingStep(str, enum.Enum):
    ORGANIZATION_SETUP = "ORGANIZATION_SETUP"
    CONNECT_INFRASTRUCTURE = "CONNECT_INFRASTRUCTURE"
    CONNECT_MONITORING = "CONNECT_MONITORING"
    CONNECT_SOURCE_CONTROL = "CONNECT_SOURCE_CONTROL"
    RUN_DISCOVERY = "RUN_DISCOVERY"
    GENERATE_SERVICE_CATALOG = "GENERATE_SERVICE_CATALOG"
    GENERATE_DEPENDENCY_GRAPH = "GENERATE_DEPENDENCY_GRAPH"
    GENERATE_RELIABILITY_REPORT = "GENERATE_RELIABILITY_REPORT"
    GENERATE_DEPLOYMENT_RISK_REPORT = "GENERATE_DEPLOYMENT_RISK_REPORT"
    FINISH = "FINISH"


class OnboardingStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class OnboardingSession(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "onboarding_sessions"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OnboardingStatus.IN_PROGRESS.value, index=True
    )
    current_step: Mapped[str] = mapped_column(
        String(40), nullable=False, default=OnboardingStep.ORGANIZATION_SETUP.value
    )
    # Steps the customer has explicitly marked complete (auto-detected steps are
    # merged on read). Stored as a list of step keys.
    completed_steps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Per-step free-form data captured during the wizard (never secrets).
    step_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recommendations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
