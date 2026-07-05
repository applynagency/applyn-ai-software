"""Sprint 65F — GitOps Progressive Delivery & Release Reliability."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0032_release_reliability"
down_revision: str | None = "0031_security_production"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()

    new_tables = [
        ("rr_release_reliability", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("release_id", sa.String(36), sa.ForeignKey("dlv_releases.id", ondelete="CASCADE"), nullable=False),
            sa.Column("deployment_id", sa.String(36), nullable=True),
            sa.Column("gitops_app_id", sa.String(36), nullable=True),
            sa.Column("environment_id", sa.String(36), sa.ForeignKey("dlv_environments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("strategy", sa.String(30), nullable=False, server_default="rolling"),
            sa.Column("stage", sa.String(40), nullable=False, server_default="init"),
            sa.Column("promotion_state", sa.String(30), nullable=False, server_default="PENDING"),
            sa.Column("verification_status", sa.String(30), nullable=False, server_default="PENDING"),
            sa.Column("baseline_version", sa.String(128), nullable=True),
            sa.Column("candidate_version", sa.String(128), nullable=True),
            sa.Column("artifact_digest", sa.String(128), nullable=True),
            sa.Column("health_gate_status", sa.String(30), nullable=True),
            sa.Column("rollback_plan", sa.Text(), nullable=True),
            sa.Column("approval_required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("timeline", sa.JSON(), nullable=False),
            sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
            sa.Column("rollout_state", sa.JSON(), nullable=False),
            sa.Column("provider_type", sa.String(40), nullable=False, server_default="k8s_rolling"),
            sa.Column("provider_mode", sa.String(20), nullable=False, server_default="offline"),
            sa.Column("status", sa.String(30), nullable=False, server_default="ACTIVE"),
            sa.Column("idempotency_key", sa.String(64), nullable=False),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_rr_release_idempotency"),
        ]),
        ("rr_verification_runs", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("reliability_id", sa.String(36), sa.ForeignKey("rr_release_reliability.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="RUNNING"),
            sa.Column("signals", sa.JSON(), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("rr_health_gate_results", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("reliability_id", sa.String(36), sa.ForeignKey("rr_release_reliability.id", ondelete="CASCADE"), nullable=False),
            sa.Column("verification_run_id", sa.String(36), nullable=True),
            sa.Column("decision", sa.String(30), nullable=False),
            sa.Column("signals", sa.JSON(), nullable=False),
            sa.Column("thresholds", sa.JSON(), nullable=False),
            sa.Column("evidence_refs", sa.JSON(), nullable=False),
            sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("rr_rollout_operations", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("reliability_id", sa.String(36), sa.ForeignKey("rr_release_reliability.id", ondelete="CASCADE"), nullable=False),
            sa.Column("operation_id", sa.String(36), nullable=True),
            sa.Column("action", sa.String(30), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
            sa.Column("traffic_steps", sa.JSON(), nullable=False),
            sa.Column("revision_history", sa.JSON(), nullable=False),
            sa.Column("result", sa.JSON(), nullable=False),
            sa.Column("simulated", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("rr_promotion_policies", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("source_tier", sa.String(20), nullable=False),
            sa.Column("target_tier", sa.String(20), nullable=False),
            sa.Column("requires_verification", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("requires_security_gate", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("digest_immutable", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("rr_promotion_requests", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("reliability_id", sa.String(36), sa.ForeignKey("rr_release_reliability.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_environment_id", sa.String(36), nullable=False),
            sa.Column("target_environment_id", sa.String(36), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
            sa.Column("block_reason", sa.Text(), nullable=True),
            sa.Column("artifact_digest", sa.String(128), nullable=True),
            sa.Column("approved_by", sa.String(36), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("rr_freeze_windows", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("environment_tier", sa.String(20), nullable=True),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("rr_rollback_records", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("reliability_id", sa.String(36), sa.ForeignKey("rr_release_reliability.id", ondelete="CASCADE"), nullable=False),
            sa.Column("operation_id", sa.String(36), nullable=True),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="RECOMMENDED"),
            sa.Column("target_revision", sa.String(128), nullable=True),
            sa.Column("automatic", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("verification", sa.JSON(), nullable=False),
            sa.Column("incident_id", sa.String(36), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
    ]
    for name, cols in new_tables:
        if name not in tables:
            op.create_table(name, *cols)
            op.create_index(f"ix_{name}_organization_id", name, ["organization_id"])
            if name == "rr_release_reliability":
                op.create_index("ix_rr_release_release_id", name, ["release_id"])
                op.create_index("ix_rr_release_status", name, ["status"])


def downgrade() -> None:
    for name in (
        "rr_rollback_records", "rr_freeze_windows", "rr_promotion_requests",
        "rr_promotion_policies", "rr_rollout_operations", "rr_health_gate_results",
        "rr_verification_runs", "rr_release_reliability",
    ):
        try:
            op.drop_table(name)
        except Exception:  # noqa: BLE001
            pass
