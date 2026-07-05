"""Sprint 67A — Customer integration onboarding sessions."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0036_integration_onboarding"
down_revision: str | None = "0035_pilot_execution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "int_onboarding_sessions" not in insp.get_table_names():
        op.create_table(
            "int_onboarding_sessions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "organization_id",
                sa.String(36),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("provider_type", sa.String(40), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
            sa.Column("environment_name", sa.String(120), nullable=True),
            sa.Column("environment_classification", sa.String(30), nullable=True),
            sa.Column("scope", sa.JSON(), nullable=False),
            sa.Column("intended_for_pilot", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("credential_id", sa.String(36), nullable=True),
            sa.Column("validation_summary", sa.JSON(), nullable=False),
            sa.Column("evidence_refs", sa.JSON(), nullable=False),
            sa.Column("required_capabilities", sa.JSON(), nullable=False),
            sa.Column("missing_capabilities", sa.JSON(), nullable=False),
            sa.Column("readiness_verdict", sa.String(30), nullable=True),
            sa.Column("registry_connection_id", sa.String(36), nullable=True),
            sa.Column("acknowledged_at", sa.String(40), nullable=True),
            sa.Column("cancellation_reason", sa.Text(), nullable=True),
            sa.Column("api_base_url", sa.String(512), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ix_int_onboarding_sessions_org",
            "int_onboarding_sessions",
            ["organization_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "int_onboarding_sessions" in insp.get_table_names():
        op.drop_index("ix_int_onboarding_sessions_org", table_name="int_onboarding_sessions")
        op.drop_table("int_onboarding_sessions")
