"""Alembic migration for DevOps delivery platform (Sprint 63B)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0023_delivery"
down_revision: str | None = "0022_control_plane"
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    tables = [
        ("dlv_source_connections", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("credential_id", sa.String(36), sa.ForeignKey("deployment_credentials.id", ondelete="CASCADE"), nullable=False),
            sa.Column("provider", sa.String(30), nullable=False),
            sa.Column("account_id", sa.String(128), nullable=False),
            sa.Column("display_name", sa.String(255), nullable=False),
            sa.Column("health", sa.String(20), nullable=False, server_default="UNKNOWN"),
            sa.Column("repository_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("dlv_repositories", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("connection_id", sa.String(36), sa.ForeignKey("dlv_source_connections.id", ondelete="CASCADE"), nullable=False),
            sa.Column("external_id", sa.String(128), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("full_name", sa.String(512), nullable=False),
            sa.Column("default_branch", sa.String(128), nullable=False, server_default="main"),
            sa.Column("visibility", sa.String(20), nullable=False, server_default="private"),
            sa.Column("url", sa.String(512), nullable=True),
            sa.Column("language", sa.String(64), nullable=True),
            sa.Column("health", sa.String(20), nullable=False, server_default="HEALTHY"),
            sa.Column("stats", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("dlv_pipelines", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("repository_id", sa.String(36), sa.ForeignKey("dlv_repositories.id", ondelete="SET NULL"), nullable=True),
            sa.Column("provider", sa.String(30), nullable=False),
            sa.Column("external_id", sa.String(128), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("dlv_pipeline_runs", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("pipeline_id", sa.String(36), sa.ForeignKey("dlv_pipelines.id", ondelete="CASCADE"), nullable=False),
            sa.Column("external_id", sa.String(128), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("branch", sa.String(128), nullable=True),
            sa.Column("commit_sha", sa.String(64), nullable=True),
            sa.Column("duration_seconds", sa.Integer(), nullable=True),
            sa.Column("url", sa.String(512), nullable=True),
            sa.Column("logs_preview", sa.Text(), nullable=True),
            sa.Column("artifacts", sa.JSON(), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("dlv_environments", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("tier", sa.String(20), nullable=False),
            sa.Column("name", sa.String(64), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cluster_id", sa.String(36), nullable=True),
            sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("freeze_window", sa.JSON(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("dlv_artifacts", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("registry_provider", sa.String(30), nullable=False),
            sa.Column("repository", sa.String(255), nullable=False),
            sa.Column("tag", sa.String(128), nullable=False),
            sa.Column("digest", sa.String(128), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("vulnerability_summary", sa.JSON(), nullable=True),
            sa.Column("promoted_to", sa.String(64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("dlv_releases", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("version", sa.String(64), nullable=False),
            sa.Column("repository_id", sa.String(36), nullable=True),
            sa.Column("artifact_id", sa.String(36), nullable=True),
            sa.Column("environment_id", sa.String(36), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
            sa.Column("risk_score", sa.Float(), nullable=True),
            sa.Column("release_notes", sa.Text(), nullable=True),
            sa.Column("rollback_plan", sa.Text(), nullable=True),
            sa.Column("dependency_graph", sa.JSON(), nullable=True),
            sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("dlv_deployments", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("release_id", sa.String(36), sa.ForeignKey("dlv_releases.id", ondelete="SET NULL"), nullable=True),
            sa.Column("environment_id", sa.String(36), sa.ForeignKey("dlv_environments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("strategy", sa.String(20), nullable=False, server_default="ROLLING"),
            sa.Column("status", sa.String(30), nullable=False, server_default="QUEUED"),
            sa.Column("image_ref", sa.String(512), nullable=True),
            sa.Column("traffic_split", sa.JSON(), nullable=True),
            sa.Column("health_validation", sa.JSON(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("dlv_security_scans", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("tool", sa.String(20), nullable=False),
            sa.Column("target", sa.String(512), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="COMPLETED"),
            sa.Column("summary", sa.JSON(), nullable=True),
            sa.Column("findings", sa.JSON(), nullable=True),
            sa.Column("sbom", sa.JSON(), nullable=True),
            sa.Column("explain", sa.Text(), nullable=True),
            sa.Column("artifact_id", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("dlv_gitops_apps", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("cluster_id", sa.String(36), nullable=True),
            sa.Column("engine", sa.String(20), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("namespace", sa.String(253), nullable=False),
            sa.Column("project", sa.String(255), nullable=True),
            sa.Column("sync_status", sa.String(30), nullable=False),
            sa.Column("health", sa.String(20), nullable=False),
            sa.Column("revision", sa.String(128), nullable=True),
            sa.Column("auto_sync", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("drift", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("history", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("dlv_operations", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("kind", sa.String(40), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING_APPROVAL"),
            sa.Column("release_id", sa.String(36), nullable=True),
            sa.Column("deployment_id", sa.String(36), nullable=True),
            sa.Column("environment_id", sa.String(36), nullable=True),
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
    ]

    for name, cols in tables:
        if not _has_table(insp, name):
            op.create_table(name, *cols)


def downgrade() -> None:
    for name in [
        "dlv_operations", "dlv_gitops_apps", "dlv_security_scans", "dlv_deployments",
        "dlv_releases", "dlv_artifacts", "dlv_environments", "dlv_pipeline_runs",
        "dlv_pipelines", "dlv_repositories", "dlv_source_connections",
    ]:
        try:
            op.drop_table(name)
        except Exception:  # noqa: BLE001
            pass
