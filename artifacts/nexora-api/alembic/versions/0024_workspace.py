"""Alembic migration for DevOps & SRE workspace (Sprint 63C)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0024_workspace"
down_revision: str | None = "0023_delivery"
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = [
        ("ws_maintenance_windows", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(30), nullable=False, server_default="WINDOW"),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="SCHEDULED"),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("impact_summary", sa.Text(), nullable=True),
            sa.Column("cluster_id", sa.String(36), nullable=True),
            sa.Column("environment_id", sa.String(36), nullable=True),
            sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("ws_daily_briefings", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("briefing_date", sa.String(10), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("sections", sa.JSON(), nullable=False),
            sa.Column("recommended_actions", sa.JSON(), nullable=False),
            sa.Column("generated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("ws_shift_handovers", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("markdown", sa.Text(), nullable=False),
            sa.Column("sections", sa.JSON(), nullable=False),
            sa.Column("generated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("ws_automation_suggestions", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("pattern", sa.Text(), nullable=False),
            sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("recommendation", sa.Text(), nullable=False),
            sa.Column("evidence", sa.JSON(), nullable=False),
            sa.Column("dismissed", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("accepted", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("ws_calendar_events", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reference_type", sa.String(40), nullable=True),
            sa.Column("reference_id", sa.String(36), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
    ]
    for name, cols in tables:
        if not _has_table(insp, name):
            op.create_table(name, *cols)


def downgrade() -> None:
    for name in [
        "ws_calendar_events", "ws_automation_suggestions", "ws_shift_handovers",
        "ws_daily_briefings", "ws_maintenance_windows",
    ]:
        try:
            op.drop_table(name)
        except Exception:  # noqa: BLE001
            pass
