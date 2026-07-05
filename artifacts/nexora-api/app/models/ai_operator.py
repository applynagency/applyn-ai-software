"""AI Platform Operator models (Sprint 64B)."""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class OperatorPolicy(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "op_policies"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    mode: Mapped[str] = mapped_column(String(30), nullable=False, default="APPROVAL_REQUIRED")
    rules: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class OperatorGoal(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "op_goals"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    target_value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="%")
    current_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    progress_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    achieved_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OperatorRecommendation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "op_recommendations"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    impact: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM")
    risk: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM")
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    referenced_resources: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    rollback_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_savings: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    simulation_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    sre_recommendation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)


class OperatorSimulation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "op_simulations"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    recommendation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("op_recommendations.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class OperatorActionProposal(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "op_action_proposals"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("op_recommendations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_APPROVAL")
    action_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    requested_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    decided_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    execution_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OperatorTimelineEntry(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "op_timeline_entries"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    recommendation_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    proposal_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class OperatorLearningRecord(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "op_learning_records"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    lesson: Mapped[str] = mapped_column(Text, nullable=False)
    record_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    recommendation_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


class OperatorExecutiveBriefing(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "op_executive_briefings"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    period_start: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    generated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
