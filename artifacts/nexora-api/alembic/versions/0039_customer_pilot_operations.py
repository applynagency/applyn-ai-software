"""Sprint 67D — Customer pilot operations reliability tables."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0039_customer_pilot_operations"
down_revision: str | None = "0038_customer_pilot_communications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()

    if "pilot_notification_deliveries" not in tables:
        op.create_table(
            "pilot_notification_deliveries",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "organization_id",
                sa.String(36),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("communication_id", sa.String(36), nullable=True),
            sa.Column("approval_id", sa.String(36), nullable=True),
            sa.Column("recipient_user_id", sa.String(36), nullable=False),
            sa.Column("channel", sa.String(20), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
            sa.Column("idempotency_key", sa.String(200), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("idempotency_key", name="uq_pilot_notification_delivery_idem"),
        )
        op.create_index(
            "ix_pilot_notification_deliveries_org",
            "pilot_notification_deliveries",
            ["organization_id"],
        )
        op.create_index(
            "ix_pilot_notification_deliveries_status",
            "pilot_notification_deliveries",
            ["status"],
        )

    if "pilot_scheduler_health_snapshots" not in tables:
        op.create_table(
            "pilot_scheduler_health_snapshots",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("job_type", sa.String(60), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("result", sa.JSON(), nullable=True),
            sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("ran_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ix_pilot_scheduler_health_job_ran",
            "pilot_scheduler_health_snapshots",
            ["job_type", "ran_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()
    if "pilot_scheduler_health_snapshots" in tables:
        op.drop_index("ix_pilot_scheduler_health_job_ran", table_name="pilot_scheduler_health_snapshots")
        op.drop_table("pilot_scheduler_health_snapshots")
    if "pilot_notification_deliveries" in tables:
        op.drop_index("ix_pilot_notification_deliveries_status", table_name="pilot_notification_deliveries")
        op.drop_index("ix_pilot_notification_deliveries_org", table_name="pilot_notification_deliveries")
        op.drop_table("pilot_notification_deliveries")
