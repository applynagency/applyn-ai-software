"""0041 — link delivery pipelines to marketplace integration connections."""

from alembic import op
import sqlalchemy as sa

revision = "0041_pipeline_integration_link"
down_revision = "0040_org_config_variables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dlv_pipelines",
        sa.Column("integration_connection_id", sa.String(36), nullable=True),
    )
    op.create_index(
        "ix_dlv_pipelines_integration",
        "dlv_pipelines",
        ["organization_id", "integration_connection_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_dlv_pipelines_integration", table_name="dlv_pipelines")
    op.drop_column("dlv_pipelines", "integration_connection_id")
