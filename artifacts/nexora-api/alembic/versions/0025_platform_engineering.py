"""Alembic migration for Platform Engineering (Sprint 64A)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0025_platform_engineering"
down_revision: str | None = "0024_workspace"
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = [
        ("pe_iac_repositories", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("provider", sa.String(30), nullable=False),
            sa.Column("url", sa.String(512), nullable=True),
            sa.Column("default_branch", sa.String(100), nullable=False, server_default="main"),
            sa.Column("working_dir", sa.String(255), nullable=False, server_default="."),
            sa.Column("credential_id", sa.String(36), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("pe_iac_stacks", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("repository_id", sa.String(36), sa.ForeignKey("pe_iac_repositories.id", ondelete="SET NULL"), nullable=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("provider", sa.String(30), nullable=False),
            sa.Column("variables", sa.JSON(), nullable=False),
            sa.Column("secret_refs", sa.JSON(), nullable=False),
            sa.Column("state_backend", sa.String(100), nullable=True),
            sa.Column("state_metadata", sa.JSON(), nullable=True),
            sa.Column("outputs", sa.JSON(), nullable=True),
            sa.Column("cloud_account_id", sa.String(36), nullable=True),
            sa.Column("cluster_id", sa.String(36), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("pe_iac_runs", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("stack_id", sa.String(36), sa.ForeignKey("pe_iac_stacks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="QUEUED"),
            sa.Column("plan_summary", sa.JSON(), nullable=True),
            sa.Column("outputs", sa.JSON(), nullable=True),
            sa.Column("logs", sa.Text(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("execution_job_id", sa.String(36), nullable=True),
            sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("pe_platform_templates", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("spec", sa.JSON(), nullable=False),
            sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("pe_environments", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("tier", sa.String(20), nullable=False),
            sa.Column("template_id", sa.String(36), sa.ForeignKey("pe_platform_templates.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING_APPROVAL"),
            sa.Column("stack_id", sa.String(36), nullable=True),
            sa.Column("cluster_id", sa.String(36), nullable=True),
            sa.Column("cloud_account_id", sa.String(36), nullable=True),
            sa.Column("components", sa.JSON(), nullable=False),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("pe_provision_runs", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("environment_id", sa.String(36), sa.ForeignKey("pe_environments.id", ondelete="SET NULL"), nullable=True),
            sa.Column("template_kind", sa.String(30), nullable=False),
            sa.Column("distribution", sa.String(30), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING_APPROVAL"),
            sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("logs", sa.Text(), nullable=True),
            sa.Column("outputs", sa.JSON(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("cluster_id", sa.String(36), nullable=True),
            sa.Column("execution_job_id", sa.String(36), nullable=True),
            sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("pe_secret_refs", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("backend", sa.String(40), nullable=False),
            sa.Column("path", sa.String(512), nullable=False),
            sa.Column("stack_id", sa.String(36), nullable=True),
            sa.Column("environment_id", sa.String(36), nullable=True),
            sa.Column("rotation_days", sa.Integer(), nullable=True),
            sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("pe_catalog_items", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("spec", sa.JSON(), nullable=False),
            sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("pe_catalog_requests", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("catalog_item_id", sa.String(36), sa.ForeignKey("pe_catalog_items.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING_APPROVAL"),
            sa.Column("params", sa.JSON(), nullable=False),
            sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("provision_id", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("pe_golden_templates", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("spec", sa.JSON(), nullable=False),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("pe_compliance_reports", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("grade", sa.String(2), nullable=False, server_default="F"),
            sa.Column("findings", sa.JSON(), nullable=False),
            sa.Column("summary", sa.JSON(), nullable=False),
            sa.Column("generated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("pe_drift_findings", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("source", sa.String(30), nullable=False),
            sa.Column("resource", sa.String(512), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False),
            sa.Column("recommendation", sa.Text(), nullable=False),
            sa.Column("ai_explanation", sa.Text(), nullable=True),
            sa.Column("stack_id", sa.String(36), nullable=True),
            sa.Column("cluster_id", sa.String(36), nullable=True),
            sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
    ]
    for name, cols in tables:
        if not _has_table(insp, name):
            op.create_table(name, *cols)


def downgrade() -> None:
    # Drop dependent tables before parents (FK-safe order).
    for name in [
        "pe_drift_findings", "pe_compliance_reports", "pe_golden_templates",
        "pe_catalog_requests", "pe_catalog_items", "pe_secret_refs",
        "pe_provision_runs", "pe_environments", "pe_platform_templates",
        "pe_iac_runs", "pe_iac_stacks", "pe_iac_repositories",
    ]:
        try:
            op.drop_table(name)
        except Exception:  # noqa: BLE001
            pass
