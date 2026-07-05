"""Organization configuration variables."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0040_org_config_variables"
down_revision: str | None = "0039_customer_pilot_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "org_config_variables" not in insp.get_table_names():
        op.create_table(
            "org_config_variables",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "organization_id",
                sa.String(36),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("key", sa.String(128), nullable=False),
            sa.Column("environment", sa.String(40), nullable=False, server_default="default"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("value_plain", sa.Text(), nullable=True),
            sa.Column("value_encrypted", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("organization_id", "key", "environment", name="uq_org_config_key_env"),
        )
        op.create_index("ix_org_config_variables_org", "org_config_variables", ["organization_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "org_config_variables" in insp.get_table_names():
        op.drop_index("ix_org_config_variables_org", table_name="org_config_variables")
        op.drop_table("org_config_variables")
