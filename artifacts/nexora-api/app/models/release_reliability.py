"""GitOps Progressive Delivery & Release Reliability models (Sprint 65F)."""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class RrReleaseReliability(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "rr_release_reliability"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_rr_release_idempotency"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    release_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dlv_releases.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    deployment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    gitops_app_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    environment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dlv_environments.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    strategy: Mapped[str] = mapped_column(String(30), nullable=False, default="rolling")
    stage: Mapped[str] = mapped_column(String(40), nullable=False, default="init")
    promotion_state: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    baseline_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    candidate_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    artifact_digest: Mapped[str | None] = mapped_column(String(128), nullable=True)
    health_gate_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    rollback_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timeline: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    rollout_state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False, default="k8s_rolling")
    provider_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="offline")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)


class RrVerificationRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "rr_verification_runs"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    reliability_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rr_release_reliability.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="RUNNING")
    signals: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RrHealthGateResult(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "rr_health_gate_results"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    reliability_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rr_release_reliability.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    verification_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    signals: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    thresholds: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evaluated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)


class RrRolloutOperation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "rr_rollout_operations"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    reliability_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rr_release_reliability.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    operation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    traffic_steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    revision_history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)


class RrPromotionPolicy(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "rr_promotion_policies"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    target_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    requires_verification: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_security_gate: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    digest_immutable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class RrPromotionRequest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "rr_promotion_requests"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    reliability_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rr_release_reliability.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    source_environment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_environment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_digest: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class RrFreezeWindow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "rr_freeze_windows"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    environment_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    starts_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)


class RrRollbackRecord(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "rr_rollback_records"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    reliability_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rr_release_reliability.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    operation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="RECOMMENDED")
    target_revision: Mapped[str | None] = mapped_column(String(128), nullable=True)
    automatic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    incident_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
