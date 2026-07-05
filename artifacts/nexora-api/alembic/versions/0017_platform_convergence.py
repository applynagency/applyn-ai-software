"""Final platform convergence (Sprint 62A).

Adds the canonical cross-cutting platform tables:

* ``domain_events``          — event bus outbox / event store (publish + replay + DLQ)
* ``notification_templates`` — channel templates (global + org overrides, localized)
* ``notification_messages``  — outbound deliveries with retries + delivery tracking
* ``activity_entries``       — unified activity feed
* ``config_entries``         — global → organization → user configuration + flags
* ``plugins``                — plugin catalog (capability manifest)
* ``organization_plugins``   — per-org plugin installation + lifecycle
* ``execution_checkpoints``  — unified execution-engine checkpoints (resume)

Idempotent: guarded by the live inspector so it is safe to re-run.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0017_platform_convergence"
down_revision: str | None = "0016_ai_platform"
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # --- domain_events ------------------------------------------------------
    if not _has_table(insp, "domain_events"):
        op.create_table(
            "domain_events",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=True),
            sa.Column("event_type", sa.String(length=120), nullable=False),
            sa.Column("aggregate_type", sa.String(length=80), nullable=True),
            sa.Column("aggregate_id", sa.String(length=64), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("source", sa.String(length=80), nullable=False, server_default="platform"),
            sa.Column("actor_id", sa.String(length=36), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_domain_events_org_type", "domain_events",
                        ["organization_id", "event_type"])
        op.create_index("ix_domain_events_status_created", "domain_events",
                        ["status", "created_at"])
        op.create_index("ix_domain_events_aggregate", "domain_events",
                        ["aggregate_type", "aggregate_id"])

    # --- notification_templates --------------------------------------------
    if not _has_table(insp, "notification_templates"):
        op.create_table(
            "notification_templates",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=True),
            sa.Column("key", sa.String(length=120), nullable=False),
            sa.Column("channel", sa.String(length=30), nullable=False),
            sa.Column("locale", sa.String(length=10), nullable=False, server_default="en"),
            sa.Column("subject_template", sa.Text(), nullable=True),
            sa.Column("body_template", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("organization_id", "key", "channel", "locale",
                                name="uq_notif_template_scope"),
        )
        op.create_index("ix_notification_templates_key", "notification_templates", ["key"])

    # --- notification_messages ---------------------------------------------
    if not _has_table(insp, "notification_messages"):
        op.create_table(
            "notification_messages",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=True),
            sa.Column("channel", sa.String(length=30), nullable=False),
            sa.Column("recipient", sa.String(length=320), nullable=False),
            sa.Column("template_key", sa.String(length=120), nullable=True),
            sa.Column("locale", sa.String(length=10), nullable=False, server_default="en"),
            sa.Column("subject", sa.Text(), nullable=True),
            sa.Column("body", sa.Text(), nullable=False, server_default=""),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("provider", sa.String(length=40), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="4"),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("provider_message_id", sa.String(length=120), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_notification_messages_org_status", "notification_messages",
                        ["organization_id", "status"])

    # --- activity_entries ---------------------------------------------------
    if not _has_table(insp, "activity_entries"):
        op.create_table(
            "activity_entries",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=True),
            sa.Column("actor_id", sa.String(length=36), nullable=True),
            sa.Column("event_type", sa.String(length=120), nullable=False),
            sa.Column("verb", sa.String(length=60), nullable=False),
            sa.Column("object_type", sa.String(length=80), nullable=True),
            sa.Column("object_id", sa.String(length=64), nullable=True),
            sa.Column("summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_activity_entries_org_created", "activity_entries",
                        ["organization_id", "created_at"])
        op.create_index("ix_activity_entries_actor", "activity_entries",
                        ["actor_id", "created_at"])
        op.create_index("ix_activity_entries_object", "activity_entries",
                        ["object_type", "object_id"])

    # --- config_entries -----------------------------------------------------
    if not _has_table(insp, "config_entries"):
        op.create_table(
            "config_entries",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("scope", sa.String(length=20), nullable=False),
            sa.Column("scope_id", sa.String(length=36), nullable=True),
            sa.Column("key", sa.String(length=160), nullable=False),
            sa.Column("value", sa.JSON(), nullable=True),
            sa.Column("value_type", sa.String(length=20), nullable=False, server_default="json"),
            sa.Column("is_feature_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_secret_ref", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("updated_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("scope", "scope_id", "key", name="uq_config_scope_key"),
        )
        op.create_index("ix_config_entries_lookup", "config_entries",
                        ["scope", "scope_id", "key"])

    # --- plugins ------------------------------------------------------------
    if not _has_table(insp, "plugins"):
        op.create_table(
            "plugins",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("slug", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("version", sa.String(length=40), nullable=False, server_default="1.0.0"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("author", sa.String(length=160), nullable=True),
            sa.Column("capabilities", sa.JSON(), nullable=True),
            sa.Column("manifest", sa.JSON(), nullable=True),
            sa.Column("is_listed", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("slug", name="uq_plugin_slug"),
        )

    # --- organization_plugins ----------------------------------------------
    if not _has_table(insp, "organization_plugins"):
        op.create_table(
            "organization_plugins",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=False),
            sa.Column("plugin_slug", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="installed"),
            sa.Column("version", sa.String(length=40), nullable=False, server_default="1.0.0"),
            sa.Column("config", sa.JSON(), nullable=True),
            sa.Column("installed_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["installed_by"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("organization_id", "plugin_slug", name="uq_org_plugin"),
        )
        op.create_index("ix_organization_plugins_org", "organization_plugins",
                        ["organization_id", "status"])

    # --- execution_checkpoints ---------------------------------------------
    if not _has_table(insp, "execution_checkpoints"):
        op.create_table(
            "execution_checkpoints",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("job_id", sa.String(length=36), nullable=False),
            sa.Column("organization_id", sa.String(length=36), nullable=True),
            sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("label", sa.String(length=120), nullable=True),
            sa.Column("state", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("job_id", "sequence", name="uq_checkpoint_job_seq"),
        )
        op.create_index("ix_execution_checkpoints_job", "execution_checkpoints",
                        ["job_id", "sequence"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    for table in (
        "execution_checkpoints",
        "organization_plugins",
        "plugins",
        "config_entries",
        "activity_entries",
        "notification_messages",
        "notification_templates",
        "domain_events",
    ):
        if _has_table(insp, table):
            op.drop_table(table)
