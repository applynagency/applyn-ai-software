"""Sprint 65E — Security Platform production integration."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0031_security_production"
down_revision: str | None = "0030_security_platform"
branch_labels = None
depends_on = None


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()

    if "sec_findings" in tables:
        _add_column_if_missing("sec_findings", sa.Column("source_system", sa.String(40), nullable=True))
        _add_column_if_missing("sec_findings", sa.Column("source_record_id", sa.String(36), nullable=True))
        _add_column_if_missing("sec_findings", sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True))
        _add_column_if_missing(
            "sec_findings",
            sa.Column("sla_breached", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        try:
            op.create_index("ix_sec_findings_source_record", "sec_findings", ["organization_id", "source_system", "source_record_id"])
        except Exception:  # noqa: BLE001
            pass

    if "sec_scan_runs" in tables:
        _add_column_if_missing("sec_scan_runs", sa.Column("provider_mode", sa.String(20), nullable=True))
        _add_column_if_missing("sec_scan_runs", sa.Column("provider_id", sa.String(36), nullable=True))
        _add_column_if_missing("sec_scan_runs", sa.Column("execution_job_id", sa.String(36), nullable=True))
        _add_column_if_missing("sec_scan_runs", sa.Column("raw_output_redacted", sa.Text(), nullable=True))

    if "sec_remediation_proposals" in tables:
        _add_column_if_missing("sec_remediation_proposals", sa.Column("execution_job_id", sa.String(36), nullable=True))
        _add_column_if_missing("sec_remediation_proposals", sa.Column("verification_evidence", sa.JSON(), nullable=True))

    new_tables = [
        ("sec_providers", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("provider_type", sa.String(40), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("config", sa.JSON(), nullable=False),
            sa.Column("mode", sa.String(20), nullable=False, server_default="unavailable"),
            sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("validation_message", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("organization_id", "provider_type", name="uq_sec_providers_org_type"),
        ]),
        ("sec_sbom_components", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("sbom_ref_id", sa.String(36), sa.ForeignKey("sec_sbom_refs.id", ondelete="CASCADE"), nullable=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("version", sa.String(120), nullable=True),
            sa.Column("ecosystem", sa.String(80), nullable=True),
            sa.Column("license", sa.String(120), nullable=True),
            sa.Column("purl", sa.String(512), nullable=True),
            sa.Column("parent_purl", sa.String(512), nullable=True),
            sa.Column("artifact_id", sa.String(36), nullable=True),
            sa.Column("vuln_finding_ids", sa.JSON(), nullable=False),
            sa.Column("normalized_key", sa.String(128), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("organization_id", "normalized_key", name="uq_sec_sbom_components_norm"),
        ]),
        ("sec_backfill_jobs", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("counts", sa.JSON(), nullable=False),
            sa.Column("started_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("sec_sla_policies", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False),
            sa.Column("environment", sa.String(80), nullable=True),
            sa.Column("due_days", sa.Integer(), nullable=False, server_default="7"),
            sa.Column("warning_hours", sa.Integer(), nullable=False, server_default="24"),
            sa.Column("owner_team", sa.String(120), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("sec_remediation_executions", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("proposal_id", sa.String(36), sa.ForeignKey("sec_remediation_proposals.id", ondelete="CASCADE"), nullable=False),
            sa.Column("execution_job_id", sa.String(36), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("checkpoints", sa.JSON(), nullable=False),
            sa.Column("result", sa.JSON(), nullable=False),
            sa.Column("rollback_metadata", sa.JSON(), nullable=False),
            sa.Column("verification", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
    ]
    for name, cols in new_tables:
        if name not in tables:
            op.create_table(name, *cols)
            op.create_index(f"ix_{name}_organization_id", name, ["organization_id"])


def downgrade() -> None:
    for name in (
        "sec_remediation_executions", "sec_sla_policies", "sec_backfill_jobs",
        "sec_sbom_components", "sec_providers",
    ):
        try:
            op.drop_table(name)
        except Exception:  # noqa: BLE001
            pass
    for table, col in (
        ("sec_remediation_proposals", "verification_evidence"),
        ("sec_remediation_proposals", "execution_job_id"),
        ("sec_scan_runs", "raw_output_redacted"),
        ("sec_scan_runs", "execution_job_id"),
        ("sec_scan_runs", "provider_id"),
        ("sec_scan_runs", "provider_mode"),
        ("sec_findings", "sla_breached"),
        ("sec_findings", "imported_at"),
        ("sec_findings", "source_record_id"),
        ("sec_findings", "source_system"),
    ):
        try:
            op.drop_column(table, col)
        except Exception:  # noqa: BLE001
            pass
