"""GA readiness (Sprint 64A).

Install runs, backup catalog, restore history, support tokens, compliance
reports, and customer success progress. Idempotent — safe to re-run.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0021_ga_readiness"
down_revision: str | None = "0020_autonomous_sre"
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if not _has_table(insp, "ga_install_runs"):
        op.create_table(
            "ga_install_runs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36),
                      sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("version", sa.String(40), nullable=False, server_default="1.0.0"),
            sa.Column("checks", sa.JSON(), nullable=True),
            sa.Column("readiness_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("readiness_report", sa.JSON(), nullable=True),
            sa.Column("sample_data_loaded", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("admin_bootstrapped", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    if not _has_table(insp, "ga_backup_records"):
        op.create_table(
            "ga_backup_records",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36),
                      sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
            sa.Column("label", sa.String(200), nullable=False, server_default=""),
            sa.Column("storage_path", sa.String(500), nullable=False, server_default=""),
            sa.Column("encrypted", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("size_bytes", sa.Integer(), nullable=True),
            sa.Column("checksum", sa.String(128), nullable=True),
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("retention_days", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("schedule_cadence", sa.String(20), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_ga_backup_org_created", "ga_backup_records",
                        ["organization_id", "created_at"])

    if not _has_table(insp, "ga_restore_history"):
        op.create_table(
            "ga_restore_history",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("backup_id", sa.String(36),
                      sa.ForeignKey("ga_backup_records.id", ondelete="CASCADE"), nullable=False),
            sa.Column("organization_id", sa.String(36), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("initiated_by", sa.String(36), nullable=True),
            sa.Column("result", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_ga_restore_backup", "ga_restore_history", ["backup_id"])

    if not _has_table(insp, "ga_support_tokens"):
        op.create_table(
            "ga_support_tokens",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=True),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("scope", sa.String(40), nullable=False, server_default="diagnostics"),
            sa.Column("read_only", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(36), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("audit_meta", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_ga_support_tokens_hash", "ga_support_tokens", ["token_hash"])

    if not _has_table(insp, "ga_compliance_reports"):
        op.create_table(
            "ga_compliance_reports",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36),
                      sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("framework", sa.String(40), nullable=False),
            sa.Column("evidence", sa.JSON(), nullable=True),
            sa.Column("gaps", sa.JSON(), nullable=True),
            sa.Column("readiness_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("generated_by", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_ga_compliance_org_fw", "ga_compliance_reports",
                        ["organization_id", "framework"])

    if not _has_table(insp, "ga_customer_success"):
        op.create_table(
            "ga_customer_success",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36),
                      sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("milestones", sa.JSON(), nullable=True),
            sa.Column("adoption_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("recommendations", sa.JSON(), nullable=True),
            sa.Column("setup_complete", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    for table in (
        "ga_customer_success", "ga_compliance_reports", "ga_support_tokens",
        "ga_restore_history", "ga_backup_records", "ga_install_runs",
    ):
        op.drop_table(table)
