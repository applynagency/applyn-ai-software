"""Control plane tables (Sprint 63A — Multi-Cloud & Kubernetes)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0022_control_plane"
down_revision: str | None = "0021_ga_readiness"
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    tables = [
        ("cp_cloud_accounts", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("credential_id", sa.String(36), sa.ForeignKey("deployment_credentials.id", ondelete="CASCADE"), nullable=False),
            sa.Column("provider", sa.String(30), nullable=False),
            sa.Column("account_id", sa.String(128), nullable=False),
            sa.Column("display_name", sa.String(255), nullable=False),
            sa.Column("regions", sa.JSON(), nullable=True),
            sa.Column("health", sa.String(20), nullable=False, server_default="UNKNOWN"),
            sa.Column("cost_summary", sa.JSON(), nullable=True),
            sa.Column("permissions", sa.JSON(), nullable=True),
            sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_sync_status", sa.String(30), nullable=True),
            sa.Column("resource_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("cp_cloud_sync_runs", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("cloud_account_id", sa.String(36), sa.ForeignKey("cp_cloud_accounts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="RUNNING"),
            sa.Column("resources_added", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("resources_total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("cp_cloud_inventory", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("cloud_account_id", sa.String(36), nullable=False),
            sa.Column("provider", sa.String(30), nullable=False),
            sa.Column("account", sa.String(128), nullable=False),
            sa.Column("region", sa.String(64), nullable=False),
            sa.Column("resource_id", sa.String(256), nullable=False),
            sa.Column("resource_type", sa.String(64), nullable=False),
            sa.Column("resource_name", sa.String(255), nullable=False),
            sa.Column("tags", sa.JSON(), nullable=True),
            sa.Column("health", sa.String(20), nullable=False, server_default="UNKNOWN"),
            sa.Column("owner", sa.String(128), nullable=True),
            sa.Column("environment", sa.String(64), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("cp_kubernetes_clusters", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("credential_id", sa.String(36), sa.ForeignKey("deployment_credentials.id", ondelete="CASCADE"), nullable=False),
            sa.Column("cloud_account_id", sa.String(36), sa.ForeignKey("cp_cloud_accounts.id", ondelete="SET NULL"), nullable=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("distribution", sa.String(30), nullable=False, server_default="VANILLA"),
            sa.Column("version", sa.String(40), nullable=True),
            sa.Column("api_endpoint", sa.String(512), nullable=True),
            sa.Column("context", sa.String(255), nullable=True),
            sa.Column("health", sa.String(20), nullable=False, server_default="UNKNOWN"),
            sa.Column("node_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("namespace_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("labels", sa.JSON(), nullable=True),
            sa.Column("last_discovery_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("cp_cluster_discovery_runs", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("cluster_id", sa.String(36), sa.ForeignKey("cp_kubernetes_clusters.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="RUNNING"),
            sa.Column("resource_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("cp_cluster_resources", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("cluster_id", sa.String(36), nullable=False),
            sa.Column("kind", sa.String(64), nullable=False),
            sa.Column("namespace", sa.String(253), nullable=True),
            sa.Column("name", sa.String(253), nullable=False),
            sa.Column("uid", sa.String(128), nullable=False),
            sa.Column("labels", sa.JSON(), nullable=True),
            sa.Column("annotations", sa.JSON(), nullable=True),
            sa.Column("health", sa.String(20), nullable=False, server_default="UNKNOWN"),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("cp_operations", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("cluster_id", sa.String(36), nullable=True),
            sa.Column("kind", sa.String(40), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING_APPROVAL"),
            sa.Column("namespace", sa.String(253), nullable=True),
            sa.Column("resource_name", sa.String(253), nullable=True),
            sa.Column("params", sa.JSON(), nullable=True),
            sa.Column("result", sa.JSON(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("cp_policy_findings", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("cluster_id", sa.String(36), nullable=False),
            sa.Column("policy", sa.String(64), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False),
            sa.Column("resource_kind", sa.String(64), nullable=False),
            sa.Column("resource_name", sa.String(253), nullable=False),
            sa.Column("namespace", sa.String(253), nullable=True),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("recommendation", sa.Text(), nullable=False),
            sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("cp_cost_snapshots", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("scope_type", sa.String(20), nullable=False),
            sa.Column("scope_id", sa.String(36), nullable=False),
            sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
            sa.Column("period_days", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("total_estimate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("breakdown", sa.JSON(), nullable=True),
            sa.Column("opportunities", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
    ]

    for name, cols in tables:
        if not _has_table(insp, name):
            op.create_table(name, *cols)


def downgrade() -> None:
    for name in [
        "cp_cost_snapshots", "cp_policy_findings", "cp_operations", "cp_cluster_resources",
        "cp_cluster_discovery_runs", "cp_kubernetes_clusters", "cp_cloud_inventory",
        "cp_cloud_sync_runs", "cp_cloud_accounts",
    ]:
        try:
            op.drop_table(name)
        except Exception:  # noqa: BLE001
            pass
