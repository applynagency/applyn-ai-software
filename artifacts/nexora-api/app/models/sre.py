"""Autonomous SRE platform models (Sprint 63B)."""

from __future__ import annotations

import enum

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, DateTime

from app.database.base import Base, TimestampMixin, UUIDMixin


class CommanderStatus(str, enum.Enum):
    OBSERVING = "OBSERVING"
    PLANNING = "PLANNING"
    INVESTIGATING = "INVESTIGATING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    SUMMARIZING = "SUMMARIZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RunbookExecutionStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class PredictionType(str, enum.Enum):
    INCIDENT_PROBABILITY = "INCIDENT_PROBABILITY"
    SLO_BREACH = "SLO_BREACH"
    CAPACITY_EXHAUSTION = "CAPACITY_EXHAUSTION"
    DEPLOYMENT_FAILURE = "DEPLOYMENT_FAILURE"
    RECURRING_INCIDENT = "RECURRING_INCIDENT"


class SRECommanderRun(Base, UUIDMixin, TimestampMixin):
    """Links an incident to an AgentRuntime commander loop."""

    __tablename__ = "sre_commander_runs"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    incident_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=CommanderStatus.OBSERVING.value)
    investigation_plan: Mapped[list | None] = mapped_column(JSON, nullable=True)
    findings_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    remediation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    postmortem_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    __table_args__ = (
        Index("ix_sre_commander_org_incident", "organization_id", "incident_id"),
    )


class SRERCAHypothesis(Base, UUIDMixin, TimestampMixin):
    """Confidence-scored RCA hypothesis with grounded evidence."""

    __tablename__ = "sre_rca_hypotheses"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    incident_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.0)
    evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")

    __table_args__ = (
        Index("ix_sre_rca_org_incident", "organization_id", "incident_id"),
    )


class SRERunbookExecution(Base, UUIDMixin, TimestampMixin):
    """Executable runbook run tracked via ExecutionEngine."""

    __tablename__ = "sre_runbook_executions"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    runbook_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=RunbookExecutionStatus.PENDING.value)
    variables: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    steps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checkpoints: Mapped[list | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_sre_runbook_exec_org", "organization_id", "runbook_id"),
    )


class SREReliabilityPrediction(Base, UUIDMixin, TimestampMixin):
    """Predictive reliability forecast with explanation."""

    __tablename__ = "sre_reliability_predictions"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    prediction_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    target: Mapped[str] = mapped_column(String(200), nullable=False, default="organization")
    score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False, default="LOW")
    horizon_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_sre_pred_org_type", "organization_id", "prediction_type"),
    )


class SREAIRecommendation(Base, UUIDMixin, TimestampMixin):
    """Explainable AI recommendation bundle."""

    __tablename__ = "sre_ai_recommendations"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False, default="incident")
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.0)
    evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)
    affected_resources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    reasoning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieved_sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    generated_actions: Mapped[list | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_sre_ai_rec_org_resource", "organization_id", "resource_type", "resource_id"),
    )
