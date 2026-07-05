"""Sprint 65G — Production integrations, credential validation & operational readiness."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0033_integration_readiness"
down_revision: str | None = "0032_release_reliability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()

    new_tables = [
        ("int_connection_registry", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("resource_type", sa.String(40), nullable=False),
            sa.Column("resource_id", sa.String(36), nullable=False),
            sa.Column("provider_type", sa.String(40), nullable=False),
            sa.Column("credential_id", sa.String(36), nullable=True),
            sa.Column("lifecycle_state", sa.String(30), nullable=False, server_default="DRAFT"),
            sa.Column("provider_mode", sa.String(20), nullable=False, server_default="unavailable"),
            sa.Column("capabilities", sa.JSON(), nullable=False),
            sa.Column("health_score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failure_reason", sa.Text(), nullable=True),
            sa.Column("validation_metadata", sa.JSON(), nullable=False),
            sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_successful_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reauth_required", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("idempotency_key", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_int_registry_idempotency"),
        ]),
        ("int_health_history", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("registry_id", sa.String(36), sa.ForeignKey("int_connection_registry.id", ondelete="CASCADE"), nullable=False),
            sa.Column("previous_state", sa.String(30), nullable=True),
            sa.Column("new_state", sa.String(30), nullable=False),
            sa.Column("probe_result", sa.JSON(), nullable=False),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("int_expiry_reminder", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("registry_id", sa.String(36), sa.ForeignKey("int_connection_registry.id", ondelete="CASCADE"), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("warning_level", sa.String(10), nullable=False, server_default="30d"),
            sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
        ("int_live_evidence", [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=False),
            sa.Column("registry_id", sa.String(36), nullable=True),
            sa.Column("operation_type", sa.String(40), nullable=False),
            sa.Column("operation_id", sa.String(36), nullable=True),
            sa.Column("correlation_id", sa.String(64), nullable=True),
            sa.Column("outcome", sa.String(30), nullable=False),
            sa.Column("blocked_reason", sa.Text(), nullable=True),
            sa.Column("evidence", sa.JSON(), nullable=False),
            sa.Column("verification", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]),
    ]
    for name, cols in new_tables:
        if name not in tables:
            op.create_table(name, *cols)
            op.create_index(f"ix_{name}_organization_id", name, ["organization_id"])
            if name == "int_connection_registry":
                op.create_index("ix_int_registry_resource", name, ["organization_id", "resource_type", "resource_id"])


def downgrade() -> None:
    for name in ("int_live_evidence", "int_expiry_reminder", "int_health_history", "int_connection_registry"):
        try:
            op.drop_table(name)
        except Exception:  # noqa: BLE001
            pass
