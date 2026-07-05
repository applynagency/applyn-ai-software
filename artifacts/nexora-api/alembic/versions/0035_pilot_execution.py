"""Sprint 66B — Real pilot execution readiness tables."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0035_pilot_execution"
down_revision: str | None = "0034_pilot_readiness"
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def _has_column(insp, table: str, column: str) -> bool:
    if table not in insp.get_table_names():
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if _has_table(insp, "pilot_enrollments"):
        for col, coltype in (
            ("execution_status", sa.String(20)),
            ("kill_switch", sa.Boolean()),
            ("operation_count", sa.Integer()),
            ("operation_limit", sa.Integer()),
            ("cooldown_minutes", sa.Integer()),
            ("last_mutation_at", sa.DateTime(timezone=True)),
            ("current_stage", sa.String(40)),
        ):
            if not _has_column(insp, "pilot_enrollments", col):
                if col == "kill_switch":
                    op.add_column("pilot_enrollments", sa.Column(col, coltype, nullable=False, server_default=sa.false()))
                elif col in ("operation_count",):
                    op.add_column("pilot_enrollments", sa.Column(col, coltype, nullable=False, server_default="0"))
                elif col in ("operation_limit",):
                    op.add_column("pilot_enrollments", sa.Column(col, coltype, nullable=False, server_default="5"))
                elif col in ("cooldown_minutes",):
                    op.add_column("pilot_enrollments", sa.Column(col, coltype, nullable=False, server_default="30"))
                elif col == "execution_status":
                    op.add_column("pilot_enrollments", sa.Column(col, coltype, nullable=False, server_default="NOT_STARTED"))
                else:
                    op.add_column("pilot_enrollments", sa.Column(col, coltype, nullable=True))

    if _has_table(insp, "pilot_live_operations"):
        for col, coltype in (
            ("template_id", sa.String(40)),
            ("params", sa.JSON()),
            ("payload_hash", sa.String(64)),
            ("approval_id", sa.String(36)),
            ("before_state", sa.JSON()),
            ("after_state", sa.JSON()),
            ("verification_status", sa.String(30)),
            ("source_mode", sa.String(20)),
            ("rollback_plan", sa.Text()),
        ):
            if not _has_column(insp, "pilot_live_operations", col):
                if col in ("params", "before_state", "after_state"):
                    op.add_column("pilot_live_operations", sa.Column(col, coltype, nullable=True))
                else:
                    op.add_column("pilot_live_operations", sa.Column(col, coltype, nullable=True))

    new_tables = [
        ("pilot_stages", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("enrollment_id", sa.String(36), sa.ForeignKey("pilot_enrollments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("stage_key", sa.String(40), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("owner_id", sa.String(36), nullable=True),
            sa.Column("evidence", sa.JSON(), nullable=False),
            sa.Column("blockers", sa.JSON(), nullable=False),
            sa.Column("rollback_plan", sa.Text(), nullable=True),
            sa.Column("outcome", sa.String(255), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("enrollment_id", "stage_key", name="uq_pilot_stage_enrollment_key"),
        ]),
        ("pilot_approvals", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("enrollment_id", sa.String(36), sa.ForeignKey("pilot_enrollments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("operation_id", sa.String(36), sa.ForeignKey("pilot_live_operations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("approver_name", sa.String(255), nullable=False),
            sa.Column("approver_email", sa.String(255), nullable=False),
            sa.Column("operation_summary", sa.Text(), nullable=False),
            sa.Column("target_environment", sa.String(255), nullable=False),
            sa.Column("rollback_plan", sa.Text(), nullable=False),
            sa.Column("payload_hash", sa.String(64), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
    ]
    for name, cols in new_tables:
        if name not in insp.get_table_names():
            op.create_table(name, *cols)
            op.create_index(f"ix_{name}_organization_id", name, ["organization_id"])


def downgrade() -> None:
    for name in ("pilot_approvals", "pilot_stages"):
        try:
            op.drop_table(name)
        except Exception:  # noqa: BLE001
            pass
