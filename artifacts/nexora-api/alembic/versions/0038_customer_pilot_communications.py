"""Sprint 67C — Customer pilot communications, preferences, reminder dedupe."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0038_customer_pilot_communications"
down_revision: str | None = "0037_customer_pilot_portal"
branch_labels = None
depends_on = None


def _widen_alembic_version_column() -> None:
    """Revision ids like 0038_customer_pilot_communications exceed varchar(32)."""
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")


def upgrade() -> None:
    _widen_alembic_version_column()
    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()

    if "pilot_customer_communications" not in tables:
        op.create_table(
            "pilot_customer_communications",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "organization_id",
                sa.String(36),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("enrollment_id", sa.String(36), nullable=True),
            sa.Column("operation_id", sa.String(36), nullable=True),
            sa.Column("category", sa.String(40), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("template_key", sa.String(80), nullable=True),
            sa.Column("deep_link", sa.String(500), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=False),
            sa.Column("recipient_user_ids", sa.JSON(), nullable=False),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("acknowledgements", sa.JSON(), nullable=False),
            sa.Column("meta", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ix_pilot_customer_communications_org",
            "pilot_customer_communications",
            ["organization_id"],
        )

    if "pilot_communication_comments" not in tables:
        op.create_table(
            "pilot_communication_comments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "organization_id",
                sa.String(36),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("communication_id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ix_pilot_communication_comments_comm",
            "pilot_communication_comments",
            ["communication_id"],
        )

    if "pilot_notification_preferences" not in tables:
        op.create_table(
            "pilot_notification_preferences",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "organization_id",
                sa.String(36),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("in_app_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("approval_reminders_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("evidence_ready_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("closeout_notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "organization_id", "user_id", name="uq_pilot_notification_prefs_org_user",
            ),
        )

    if "pilot_approval_reminder_deliveries" not in tables:
        op.create_table(
            "pilot_approval_reminder_deliveries",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "organization_id",
                sa.String(36),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("approval_id", sa.String(36), nullable=False),
            sa.Column("reminder_type", sa.String(20), nullable=False),
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "approval_id", "reminder_type", name="uq_pilot_approval_reminder_type",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()
    if "pilot_approval_reminder_deliveries" in tables:
        op.drop_table("pilot_approval_reminder_deliveries")
    if "pilot_notification_preferences" in tables:
        op.drop_table("pilot_notification_preferences")
    if "pilot_communication_comments" in tables:
        op.drop_index("ix_pilot_communication_comments_comm", table_name="pilot_communication_comments")
        op.drop_table("pilot_communication_comments")
    if "pilot_customer_communications" in tables:
        op.drop_index("ix_pilot_customer_communications_org", table_name="pilot_customer_communications")
        op.drop_table("pilot_customer_communications")
