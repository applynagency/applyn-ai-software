"""Alembic migration for Enterprise Observability Platform (Sprint 65B)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0028_observability_platform"
down_revision: str | None = "0027_k8s_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = [
        ("obs_integrations", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("signal", sa.String(20), nullable=False),
            sa.Column("config", sa.JSON(), nullable=False),
            sa.Column("credential_id", sa.String(36), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("retention_days", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("obs_saved_searches", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("signal", sa.String(20), nullable=False),
            sa.Column("query", sa.Text(), nullable=False),
            sa.Column("filters", sa.JSON(), nullable=False),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("obs_correlation_timelines", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("timeline", sa.JSON(), nullable=False),
            sa.Column("root_cause", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("obs_slo_evaluations", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("service_id", sa.String(36), nullable=True),
            sa.Column("slo_id", sa.String(36), nullable=True),
            sa.Column("objective", sa.String(30), nullable=False),
            sa.Column("target", sa.Float(), nullable=False),
            sa.Column("actual", sa.Float(), nullable=False),
            sa.Column("error_budget_remaining", sa.Float(), nullable=True),
            sa.Column("burn_rate", sa.Float(), nullable=True),
            sa.Column("compliant", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("detail", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("obs_alert_groups", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("correlation_id", sa.String(128), nullable=False),
            sa.Column("alert_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("severity", sa.String(20), nullable=False, server_default="WARNING"),
            sa.Column("summary", sa.JSON(), nullable=False),
            sa.Column("suppressed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
    ]
    for name, cols in tables:
        if name not in insp.get_table_names():
            op.create_table(name, *cols)
            op.create_index(f"ix_{name}_organization_id", name, ["organization_id"])


def downgrade() -> None:
    for name in (
        "obs_alert_groups", "obs_slo_evaluations", "obs_correlation_timelines",
        "obs_saved_searches", "obs_integrations",
    ):
        op.drop_table(name)
