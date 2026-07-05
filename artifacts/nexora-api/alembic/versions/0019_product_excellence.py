"""Product excellence (Sprint 63A).

In-app notification center, saved views, dashboard layouts, report schedules,
collaboration (comments/reactions), and product analytics tables.
Idempotent — safe to re-run.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0019_product_excellence"
down_revision: str | None = "0018_production_hardening"
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if not _has_table(insp, "inbox_notifications"):
        op.create_table(
            "inbox_notifications",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("title", sa.String(300), nullable=False, server_default=""),
            sa.Column("body", sa.Text(), nullable=False, server_default=""),
            sa.Column("category", sa.String(40), nullable=False, server_default="general"),
            sa.Column("priority", sa.String(10), nullable=False, server_default="normal"),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("pinned", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("action_url", sa.String(500), nullable=True),
            sa.Column("group_key", sa.String(120), nullable=True),
            sa.Column("source_event_id", sa.String(36), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_inbox_notifications_user_read", "inbox_notifications",
                        ["user_id", "read_at", "created_at"])
        op.create_index("ix_inbox_notifications_org_user", "inbox_notifications",
                        ["organization_id", "user_id"])

    if not _has_table(insp, "saved_views"):
        op.create_table(
            "saved_views",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("view_type", sa.String(30), nullable=False, server_default="filter"),
            sa.Column("definition", sa.JSON(), nullable=True),
            sa.Column("is_shared", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_saved_views_org_user", "saved_views", ["organization_id", "user_id"])

    if not _has_table(insp, "dashboard_layouts"):
        op.create_table(
            "dashboard_layouts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("widgets", sa.JSON(), nullable=True),
            sa.Column("is_shared", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_dashboard_layouts_org_user", "dashboard_layouts",
                        ["organization_id", "user_id"])

    if not _has_table(insp, "report_schedules"):
        op.create_table(
            "report_schedules",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("created_by", sa.String(36), nullable=True),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("report_type", sa.String(40), nullable=False, server_default="executive"),
            sa.Column("cadence", sa.String(20), nullable=False, server_default="monthly"),
            sa.Column("export_format", sa.String(10), nullable=False, server_default="pdf"),
            sa.Column("delivery_channel", sa.String(20), nullable=False, server_default="email"),
            sa.Column("delivery_target", sa.String(320), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_report_schedules_org_enabled", "report_schedules",
                        ["organization_id", "enabled"])

    if not _has_table(insp, "collaboration_comments"):
        op.create_table(
            "collaboration_comments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("resource_type", sa.String(80), nullable=False),
            sa.Column("resource_id", sa.String(64), nullable=False),
            sa.Column("parent_id", sa.String(36), nullable=True),
            sa.Column("author_id", sa.String(36), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("mentions", sa.JSON(), nullable=True),
            sa.Column("attachments", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["parent_id"], ["collaboration_comments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_collab_comments_resource", "collaboration_comments",
                        ["resource_type", "resource_id", "created_at"])

    if not _has_table(insp, "collaboration_reactions"):
        op.create_table(
            "collaboration_reactions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("comment_id", sa.String(36), nullable=True),
            sa.Column("resource_type", sa.String(80), nullable=True),
            sa.Column("resource_id", sa.String(64), nullable=True),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("emoji", sa.String(20), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["comment_id"], ["collaboration_comments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_collab_reactions_comment", "collaboration_reactions", ["comment_id"])
        op.create_index("ix_collab_reactions_resource", "collaboration_reactions",
                        ["resource_type", "resource_id"])

    if not _has_table(insp, "product_analytics_events"):
        op.create_table(
            "product_analytics_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=True),
            sa.Column("event_name", sa.String(120), nullable=False),
            sa.Column("properties", sa.JSON(), nullable=True),
            sa.Column("session_hash", sa.String(64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_product_analytics_org_event", "product_analytics_events",
                        ["organization_id", "event_name", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    for table in (
        "product_analytics_events", "collaboration_reactions", "collaboration_comments",
        "report_schedules", "dashboard_layouts", "saved_views", "inbox_notifications",
    ):
        if _has_table(insp, table):
            op.drop_table(table)
