"""Alembic migration for Enterprise DevSecOps Security Platform (Sprint 65D)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0030_security_platform"
down_revision: str | None = "0029_incident_response"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = [
        ("sec_findings", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source", sa.String(30), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="OPEN"),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("resource", sa.String(512), nullable=True),
            sa.Column("service", sa.String(200), nullable=True),
            sa.Column("environment", sa.String(80), nullable=True),
            sa.Column("owner_team", sa.String(120), nullable=True),
            sa.Column("cve", sa.String(40), nullable=True),
            sa.Column("cvss_score", sa.Float(), nullable=True),
            sa.Column("evidence", sa.JSON(), nullable=False),
            sa.Column("remediation_guidance", sa.Text(), nullable=True),
            sa.Column("fingerprint", sa.String(64), nullable=False),
            sa.Column("scan_run_id", sa.String(36), nullable=True),
            sa.Column("related_incident_id", sa.String(36), nullable=True),
            sa.Column("related_deployment_id", sa.String(36), nullable=True),
            sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("exception_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("history", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("organization_id", "fingerprint", name="uq_sec_findings_dedup"),
        ]),
        ("sec_scan_runs", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("tool", sa.String(40), nullable=False),
            sa.Column("target", sa.String(512), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="COMPLETED"),
            sa.Column("summary", sa.JSON(), nullable=False),
            sa.Column("result", sa.JSON(), nullable=False),
            sa.Column("simulated", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("gate_decision", sa.String(20), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("sec_sbom_refs", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("scan_run_id", sa.String(36), nullable=True),
            sa.Column("format", sa.String(20), nullable=False, server_default="cyclonedx"),
            sa.Column("target", sa.String(512), nullable=False),
            sa.Column("component_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("inventory", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("sec_exceptions", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("finding_id", sa.String(36), sa.ForeignKey("sec_findings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("justification", sa.Text(), nullable=False),
            sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("sec_remediation_proposals", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("finding_id", sa.String(36), sa.ForeignKey("sec_findings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(40), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("evidence", sa.JSON(), nullable=False),
            sa.Column("risk", sa.String(20), nullable=False, server_default="MEDIUM"),
            sa.Column("impact", sa.Text(), nullable=True),
            sa.Column("rollback_plan", sa.Text(), nullable=True),
            sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("status", sa.String(20), nullable=False, server_default="PROPOSED"),
            sa.Column("execution_status", sa.String(20), nullable=True),
            sa.Column("remediation_action_id", sa.String(36), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("sec_posture_snapshots", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("posture_score", sa.Integer(), nullable=False),
            sa.Column("grade", sa.String(2), nullable=False),
            sa.Column("breakdown", sa.JSON(), nullable=False),
            sa.Column("open_critical", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("sec_investigations", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("timeline", sa.JSON(), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("incident_id", sa.String(36), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("sec_access_review_campaigns", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
            sa.Column("scope", sa.JSON(), nullable=False),
            sa.Column("findings_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
    ]
    for name, cols in tables:
        if name not in insp.get_table_names():
            op.create_table(name, *cols)
            op.create_index(f"ix_{name}_organization_id", name, ["organization_id"])
            if name == "sec_findings":
                op.create_index("ix_sec_findings_severity", "sec_findings", ["severity"])
                op.create_index("ix_sec_findings_status", "sec_findings", ["status"])
                op.create_index("ix_sec_findings_fingerprint", "sec_findings", ["fingerprint"])


def downgrade() -> None:
    for name in (
        "sec_access_review_campaigns", "sec_investigations", "sec_posture_snapshots",
        "sec_remediation_proposals", "sec_exceptions", "sec_sbom_refs",
        "sec_scan_runs", "sec_findings",
    ):
        op.drop_table(name)
