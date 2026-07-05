"""Production pilot readiness models (Sprint 66A/66B)."""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin
from app.pilot.operations import PILOT_CATALOG_ACTIONS

PILOT_ALLOWED_ACTIONS = PILOT_CATALOG_ACTIONS


class PilotEnrollment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pilot_enrollments"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_pilot_enrollment_org"),)

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    onboarding_path_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    live_operations_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    execution_status: Mapped[str] = mapped_column(String(20), nullable=False, default="NOT_STARTED")
    kill_switch: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    operation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    operation_limit: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    last_mutation_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    baseline: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    contacts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PilotChecklistItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pilot_checklist_items"
    __table_args__ = (UniqueConstraint("enrollment_id", "item_key", name="uq_pilot_checklist_item"),)

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    enrollment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pilot_enrollments.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    section: Mapped[str] = mapped_column(String(40), nullable=False)
    item_key: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    blockers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PilotAssessment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pilot_assessments"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    enrollment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pilot_enrollments.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="COMPLETED")
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    recommendations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_modes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PilotScorecard(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pilot_scorecards"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    enrollment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pilot_enrollments.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    scores: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    insufficient_data: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class PilotLiveOperation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pilot_live_operations"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    enrollment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pilot_enrollments.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_name: Mapped[str] = mapped_column(String(255), nullable=False)
    environment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    cluster_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING_CONFIRMATION")
    confirmation_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    typed_confirmation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approval_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    before_state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    after_state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    verification_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rollback_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    preflight: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    verification: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    confirmed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PilotStage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pilot_stages"
    __table_args__ = (UniqueConstraint("enrollment_id", "stage_key", name="uq_pilot_stage_enrollment_key"),)

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    enrollment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pilot_enrollments.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    stage_key: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    blockers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    rollback_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PilotApproval(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pilot_approvals"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    enrollment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pilot_enrollments.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    operation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pilot_live_operations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    approver_name: Mapped[str] = mapped_column(String(255), nullable=False)
    approver_email: Mapped[str] = mapped_column(String(255), nullable=False)
    operation_summary: Mapped[str] = mapped_column(Text, nullable=False)
    target_environment: Mapped[str] = mapped_column(String(255), nullable=False)
    rollback_plan: Mapped[str] = mapped_column(Text, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
