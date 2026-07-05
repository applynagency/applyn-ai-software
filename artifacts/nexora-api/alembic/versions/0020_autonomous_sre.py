"""Autonomous SRE platform (Sprint 63B).

Commander runs, RCA hypotheses, runbook executions, reliability predictions,
and explainable AI recommendations. Idempotent — safe to re-run.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0020_autonomous_sre"
down_revision: str | None = "0019_product_excellence"
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if not _has_table(insp, "sre_commander_runs"):
        op.create_table(
            "sre_commander_runs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36),
                      sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("incident_id", sa.String(36), nullable=False),
            sa.Column("agent_run_id", sa.String(36), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="OBSERVING"),
            sa.Column("investigation_plan", sa.JSON(), nullable=True),
            sa.Column("findings_summary", sa.Text(), nullable=True),
            sa.Column("remediation_summary", sa.Text(), nullable=True),
            sa.Column("postmortem_id", sa.String(36), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_sre_commander_org_incident", "sre_commander_runs",
                        ["organization_id", "incident_id"])
        op.create_index("ix_sre_commander_runs_incident_id", "sre_commander_runs", ["incident_id"])

    if not _has_table(insp, "sre_rca_hypotheses"):
        op.create_table(
            "sre_rca_hypotheses",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36),
                      sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("incident_id", sa.String(36), nullable=False),
            sa.Column("hypothesis", sa.Text(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("evidence", sa.JSON(), nullable=True),
            sa.Column("sources", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="open"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_sre_rca_org_incident", "sre_rca_hypotheses",
                        ["organization_id", "incident_id"])

    if not _has_table(insp, "sre_runbook_executions"):
        op.create_table(
            "sre_runbook_executions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36),
                      sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("runbook_id", sa.String(36), nullable=False),
            sa.Column("job_id", sa.String(36), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
            sa.Column("variables", sa.JSON(), nullable=True),
            sa.Column("steps", sa.JSON(), nullable=True),
            sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("checkpoints", sa.JSON(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_sre_runbook_exec_org", "sre_runbook_executions",
                        ["organization_id", "runbook_id"])

    if not _has_table(insp, "sre_reliability_predictions"):
        op.create_table(
            "sre_reliability_predictions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36),
                      sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("prediction_type", sa.String(40), nullable=False),
            sa.Column("target", sa.String(200), nullable=False, server_default="organization"),
            sa.Column("score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("risk_level", sa.String(10), nullable=False, server_default="LOW"),
            sa.Column("horizon_hours", sa.Integer(), nullable=False, server_default="24"),
            sa.Column("explanation", sa.Text(), nullable=True),
            sa.Column("evidence", sa.JSON(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_sre_pred_org_type", "sre_reliability_predictions",
                        ["organization_id", "prediction_type"])

    if not _has_table(insp, "sre_ai_recommendations"):
        op.create_table(
            "sre_ai_recommendations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36),
                      sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("resource_type", sa.String(40), nullable=False, server_default="incident"),
            sa.Column("resource_id", sa.String(36), nullable=False),
            sa.Column("title", sa.String(300), nullable=False, server_default=""),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("evidence", sa.JSON(), nullable=True),
            sa.Column("affected_resources", sa.JSON(), nullable=True),
            sa.Column("reasoning_summary", sa.Text(), nullable=True),
            sa.Column("retrieved_sources", sa.JSON(), nullable=True),
            sa.Column("generated_actions", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_sre_ai_rec_org_resource", "sre_ai_recommendations",
                        ["organization_id", "resource_type", "resource_id"])


def downgrade() -> None:
    for table in (
        "sre_ai_recommendations", "sre_reliability_predictions",
        "sre_runbook_executions", "sre_rca_hypotheses", "sre_commander_runs",
    ):
        op.drop_table(table)
