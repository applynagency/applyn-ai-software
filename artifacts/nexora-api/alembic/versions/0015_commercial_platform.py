"""Commercial platform — billing, licensing, quotas & usage (Sprint 61C).

Adds the commercial tables:

* ``plans``                     — subscription plan catalog (configurable limits/features).
* ``subscriptions``             — one row per organization (plan + lifecycle + provider).
* ``usage_records``             — daily per-metric usage aggregates per org.
* ``quota_overrides``           — per-org per-metric limit overrides.
* ``licenses``                  — SaaS/on-prem/offline/enterprise licenses (signature-validated).
* ``invoices``                  — provider-issued invoices.
* ``billing_events``            — webhook outbox.
* ``billing_webhook_endpoints`` — per-org outbound webhook targets.

Idempotent: guarded by the live inspector so it is safe to re-run.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0015_commercial_platform"
down_revision: str | None = "0014_identity_platform"
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # --- plans --------------------------------------------------------------
    if not _has_table(insp, "plans"):
        op.create_table(
            "plans",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("slug", sa.String(length=120), nullable=False),
            sa.Column("tier", sa.String(length=40), nullable=False, server_default="FREE"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("limits", sa.JSON(), nullable=True),
            sa.Column("features", sa.JSON(), nullable=True),
            sa.Column("quota_policy", sa.JSON(), nullable=True),
            sa.Column("price_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
            sa.Column("billing_interval", sa.String(length=20), nullable=False, server_default="month"),
            sa.Column("trial_days", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("support_tier", sa.String(length=40), nullable=False, server_default="community"),
            sa.Column("external_price_id", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("slug", name="uq_plan_slug"),
        )
        op.create_index("ix_plans_slug", "plans", ["slug"])

    # --- subscriptions ------------------------------------------------------
    if not _has_table(insp, "subscriptions"):
        op.create_table(
            "subscriptions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=False),
            sa.Column("plan_id", sa.String(length=36), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="TRIAL"),
            sa.Column("provider", sa.String(length=20), nullable=False, server_default="MANUAL"),
            sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
            sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancel_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("external_customer_id", sa.String(length=255), nullable=True),
            sa.Column("external_subscription_id", sa.String(length=255), nullable=True),
            sa.Column("subscription_metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="RESTRICT"),
            sa.UniqueConstraint("organization_id", name="uq_subscription_org"),
        )
        op.create_index("ix_subscriptions_organization_id", "subscriptions", ["organization_id"])
        op.create_index("ix_subscriptions_plan_id", "subscriptions", ["plan_id"])
        op.create_index("ix_subscriptions_status", "subscriptions", ["status"])
        op.create_index("ix_subscriptions_external_sub", "subscriptions", ["external_subscription_id"])

    # --- usage_records ------------------------------------------------------
    if not _has_table(insp, "usage_records"):
        op.create_table(
            "usage_records",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=False),
            sa.Column("metric", sa.String(length=40), nullable=False),
            sa.Column("usage_date", sa.Date(), nullable=False),
            sa.Column("value", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("organization_id", "metric", "usage_date", name="uq_usage_org_metric_day"),
        )
        op.create_index("ix_usage_records_organization_id", "usage_records", ["organization_id"])
        op.create_index("ix_usage_records_metric", "usage_records", ["metric"])
        op.create_index("ix_usage_records_usage_date", "usage_records", ["usage_date"])

    # --- quota_overrides ----------------------------------------------------
    if not _has_table(insp, "quota_overrides"):
        op.create_table(
            "quota_overrides",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=False),
            sa.Column("metric", sa.String(length=40), nullable=False),
            sa.Column("limit_value", sa.Integer(), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("organization_id", "metric", name="uq_quota_override_org_metric"),
        )
        op.create_index("ix_quota_overrides_organization_id", "quota_overrides", ["organization_id"])

    # --- licenses -----------------------------------------------------------
    if not _has_table(insp, "licenses"):
        op.create_table(
            "licenses",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=True),
            sa.Column("license_key", sa.String(length=128), nullable=False),
            sa.Column("license_type", sa.String(length=30), nullable=False, server_default="SAAS"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
            sa.Column("plan_slug", sa.String(length=120), nullable=True),
            sa.Column("seats", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("features", sa.JSON(), nullable=True),
            sa.Column("limits", sa.JSON(), nullable=True),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("signature", sa.String(length=128), nullable=True),
            sa.Column("issued_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["issued_by"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("license_key", name="uq_license_key"),
        )
        op.create_index("ix_licenses_organization_id", "licenses", ["organization_id"])
        op.create_index("ix_licenses_license_key", "licenses", ["license_key"])
        op.create_index("ix_licenses_expires_at", "licenses", ["expires_at"])

    # --- invoices -----------------------------------------------------------
    if not _has_table(insp, "invoices"):
        op.create_table(
            "invoices",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=False),
            sa.Column("provider", sa.String(length=20), nullable=False, server_default="MANUAL"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="OPEN"),
            sa.Column("amount_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
            sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("external_id", sa.String(length=255), nullable=True),
            sa.Column("line_items", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_invoices_organization_id", "invoices", ["organization_id"])
        op.create_index("ix_invoices_status", "invoices", ["status"])
        op.create_index("ix_invoices_external_id", "invoices", ["external_id"])

    # --- billing_events -----------------------------------------------------
    if not _has_table(insp, "billing_events"):
        op.create_table(
            "billing_events",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=True),
            sa.Column("event_type", sa.String(length=60), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("delivery_status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_billing_events_organization_id", "billing_events", ["organization_id"])
        op.create_index("ix_billing_events_event_type", "billing_events", ["event_type"])
        op.create_index("ix_billing_events_delivery_status", "billing_events", ["delivery_status"])

    # --- billing_webhook_endpoints ------------------------------------------
    if not _has_table(insp, "billing_webhook_endpoints"):
        op.create_table(
            "billing_webhook_endpoints",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=False),
            sa.Column("url", sa.String(length=500), nullable=False),
            sa.Column("secret", sa.String(length=255), nullable=True),
            sa.Column("events", sa.JSON(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        )
        op.create_index(
            "ix_billing_webhook_endpoints_organization_id",
            "billing_webhook_endpoints", ["organization_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    for table in (
        "billing_webhook_endpoints",
        "billing_events",
        "invoices",
        "licenses",
        "quota_overrides",
        "usage_records",
        "subscriptions",
        "plans",
    ):
        if _has_table(insp, table):
            op.drop_table(table)
