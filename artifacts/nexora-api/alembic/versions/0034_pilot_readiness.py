"""Sprint 66A — Production pilot readiness tables."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0034_pilot_readiness"
down_revision: str | None = "0033_integration_readiness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()

    new_tables = [
        ("pilot_enrollments", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
            sa.Column("onboarding_path_id", sa.String(40), nullable=True),
            sa.Column("live_operations_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("baseline", sa.JSON(), nullable=False),
            sa.Column("contacts", sa.JSON(), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("organization_id", name="uq_pilot_enrollment_org"),
        ]),
        ("pilot_checklist_items", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("enrollment_id", sa.String(36), sa.ForeignKey("pilot_enrollments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("section", sa.String(40), nullable=False),
            sa.Column("item_key", sa.String(60), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("owner_id", sa.String(36), nullable=True),
            sa.Column("evidence", sa.JSON(), nullable=False),
            sa.Column("blockers", sa.JSON(), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("enrollment_id", "item_key", name="uq_pilot_checklist_item"),
        ]),
        ("pilot_assessments", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("enrollment_id", sa.String(36), sa.ForeignKey("pilot_enrollments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="COMPLETED"),
            sa.Column("summary", sa.JSON(), nullable=False),
            sa.Column("recommendations", sa.JSON(), nullable=False),
            sa.Column("source_modes", sa.JSON(), nullable=False),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("pilot_scorecards", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("enrollment_id", sa.String(36), sa.ForeignKey("pilot_enrollments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("scores", sa.JSON(), nullable=False),
            sa.Column("metrics", sa.JSON(), nullable=False),
            sa.Column("insufficient_data", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("pilot_live_operations", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("enrollment_id", sa.String(36), sa.ForeignKey("pilot_enrollments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("action", sa.String(40), nullable=False),
            sa.Column("resource_name", sa.String(255), nullable=False),
            sa.Column("environment_id", sa.String(36), nullable=True),
            sa.Column("cluster_id", sa.String(36), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING_CONFIRMATION"),
            sa.Column("confirmation_token", sa.String(64), nullable=True),
            sa.Column("typed_confirmation", sa.String(255), nullable=True),
            sa.Column("approved_by", sa.String(36), nullable=True),
            sa.Column("correlation_id", sa.String(64), nullable=True),
            sa.Column("preflight", sa.JSON(), nullable=False),
            sa.Column("result", sa.JSON(), nullable=False),
            sa.Column("verification", sa.JSON(), nullable=False),
            sa.Column("created_by", sa.String(36), nullable=False),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        "pilot_live_operations", "pilot_scorecards", "pilot_assessments",
        "pilot_checklist_items", "pilot_enrollments",
    ):
        try:
            op.drop_table(name)
        except Exception:  # noqa: BLE001
            pass
