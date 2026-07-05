"""Alembic migration for AI Platform Operator (Sprint 64B)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0026_operator"
down_revision: str | None = "0025_platform_engineering"
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = [
        ("op_policies", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("mode", sa.String(30), nullable=False, server_default="APPROVAL_REQUIRED"),
            sa.Column("rules", sa.JSON(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("op_goals", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("metric", sa.String(40), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("target_value", sa.Float(), nullable=False),
            sa.Column("unit", sa.String(30), nullable=False, server_default="%"),
            sa.Column("current_value", sa.Float(), nullable=True),
            sa.Column("progress_percent", sa.Float(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("op_recommendations", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("kind", sa.String(40), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
            sa.Column("impact", sa.String(20), nullable=False, server_default="MEDIUM"),
            sa.Column("risk", sa.String(20), nullable=False, server_default="MEDIUM"),
            sa.Column("evidence", sa.JSON(), nullable=False),
            sa.Column("referenced_resources", sa.JSON(), nullable=False),
            sa.Column("rollback_plan", sa.Text(), nullable=True),
            sa.Column("estimated_savings", sa.Float(), nullable=True),
            sa.Column("reasoning", sa.Text(), nullable=True),
            sa.Column("simulation_id", sa.String(36), nullable=True),
            sa.Column("sre_recommendation_id", sa.String(36), nullable=True),
            sa.Column("environment", sa.String(50), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("op_simulations", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("recommendation_id", sa.String(36), sa.ForeignKey("op_recommendations.id", ondelete="SET NULL"), nullable=True),
            sa.Column("kind", sa.String(40), nullable=False),
            sa.Column("result", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("op_action_proposals", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("recommendation_id", sa.String(36), sa.ForeignKey("op_recommendations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING_APPROVAL"),
            sa.Column("action_payload", sa.JSON(), nullable=False),
            sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("decided_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("execution_result", sa.JSON(), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("op_timeline_entries", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("detail", sa.JSON(), nullable=False),
            sa.Column("recommendation_id", sa.String(36), nullable=True),
            sa.Column("proposal_id", sa.String(36), nullable=True),
            sa.Column("actor_id", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("op_learning_records", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("source", sa.String(50), nullable=False),
            sa.Column("outcome", sa.String(30), nullable=False),
            sa.Column("lesson", sa.Text(), nullable=False),
            sa.Column("record_metadata", sa.JSON(), nullable=False),
            sa.Column("recommendation_id", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("op_executive_briefings", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column("summary", sa.JSON(), nullable=False),
            sa.Column("generated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
    ]
    for name, cols in tables:
        if not _has_table(insp, name):
            op.create_table(name, *cols)
            op.create_index(f"ix_{name}_organization_id", name, ["organization_id"])


def downgrade() -> None:
    for name in (
        "op_executive_briefings", "op_learning_records", "op_timeline_entries",
        "op_action_proposals", "op_simulations", "op_recommendations",
        "op_goals", "op_policies",
    ):
        op.drop_table(name)
