"""Sprint 67B — Customer pilot portal tables."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0037_customer_pilot_portal"
down_revision: str | None = "0036_integration_onboarding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()

    if "pilot_approval_packages" not in tables:
        op.create_table(
            "pilot_approval_packages",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "organization_id",
                sa.String(36),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("operation_id", sa.String(36), nullable=False),
            sa.Column("approval_id", sa.String(36), nullable=True),
            sa.Column("payload_hash", sa.String(64), nullable=False),
            sa.Column("rollback_plan_hash", sa.String(64), nullable=False),
            sa.Column("package", sa.JSON(), nullable=False),
            sa.Column("environment_id", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_pilot_approval_packages_org", "pilot_approval_packages", ["organization_id"])

    if "pilot_closeout_requests" not in tables:
        op.create_table(
            "pilot_closeout_requests",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "organization_id",
                sa.String(36),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("enrollment_id", sa.String(36), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING_OPERATOR_REVIEW"),
            sa.Column("outcome_rating", sa.Integer(), nullable=True),
            sa.Column("customer_comments", sa.Text(), nullable=True),
            sa.Column("signoff_contact", sa.String(255), nullable=False),
            sa.Column("follow_up_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("blockers", sa.JSON(), nullable=False),
            sa.Column("requested_by", sa.String(36), nullable=False),
            sa.Column("reviewed_at", sa.String(40), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_pilot_closeout_requests_org", "pilot_closeout_requests", ["organization_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()
    if "pilot_closeout_requests" in tables:
        op.drop_index("ix_pilot_closeout_requests_org", table_name="pilot_closeout_requests")
        op.drop_table("pilot_closeout_requests")
    if "pilot_approval_packages" in tables:
        op.drop_index("ix_pilot_approval_packages_org", table_name="pilot_approval_packages")
        op.drop_table("pilot_approval_packages")
