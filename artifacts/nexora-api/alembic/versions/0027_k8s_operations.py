"""Alembic migration for Advanced Kubernetes Operations (Sprint 65A)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0027_k8s_operations"
down_revision: str | None = "0026_operator"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "cp_k8s_diagnostics" not in insp.get_table_names():
        op.create_table(
            "cp_k8s_diagnostics",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("cluster_id", sa.String(36), sa.ForeignKey("cp_kubernetes_clusters.id", ondelete="CASCADE"), nullable=False),
            sa.Column("namespace", sa.String(253), nullable=True),
            sa.Column("resource_kind", sa.String(64), nullable=False),
            sa.Column("resource_name", sa.String(253), nullable=False),
            sa.Column("bundle", sa.JSON(), nullable=False),
            sa.Column("collected_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_cp_k8s_diagnostics_organization_id", "cp_k8s_diagnostics", ["organization_id"])
        op.create_index("ix_cp_k8s_diagnostics_cluster_id", "cp_k8s_diagnostics", ["cluster_id"])


def downgrade() -> None:
    op.drop_table("cp_k8s_diagnostics")
