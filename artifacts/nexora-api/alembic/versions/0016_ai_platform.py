"""AI Platform & Agent Runtime (Sprint 61D).

Adds the unified AI runtime tables:

* ``ai_provider_configs`` — per-org routing policy + enabled providers.
* ``prompt_templates``    — versioned prompt registry (global + org overrides).
* ``mcp_servers``         — org-registered MCP servers (remote tools).
* ``ai_agent_runs``       — agent runtime state with checkpoints for resume.
* ``ai_memory_entries``   — semantic/episodic/org/user long-term memory.
* ``ai_evaluations``      — historical AI evaluations.
* ``ai_usage_records``    — token + cost accounting per org/feature/provider/model.

Idempotent: guarded by the live inspector so it is safe to re-run.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0016_ai_platform"
down_revision: str | None = "0015_commercial_platform"
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # --- ai_provider_configs -----------------------------------------------
    if not _has_table(insp, "ai_provider_configs"):
        op.create_table(
            "ai_provider_configs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=False),
            sa.Column("routing_policy", sa.String(length=30), nullable=False,
                      server_default="highest_quality"),
            sa.Column("enabled_providers", sa.JSON(), nullable=True),
            sa.Column("preferred_models", sa.JSON(), nullable=True),
            sa.Column("default_temperature", sa.Float(), nullable=False, server_default="0.2"),
            sa.Column("default_max_tokens", sa.Integer(), nullable=False, server_default="1024"),
            sa.Column("cache_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("updated_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("organization_id", name="uq_ai_provider_config_org"),
        )
        op.create_index("ix_ai_provider_configs_organization_id",
                        "ai_provider_configs", ["organization_id"])

    # --- prompt_templates ---------------------------------------------------
    if not _has_table(insp, "prompt_templates"):
        op.create_table(
            "prompt_templates",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=True),
            sa.Column("key", sa.String(length=120), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("template", sa.Text(), nullable=False),
            sa.Column("variables", sa.JSON(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("organization_id", "key", "version",
                                name="uq_prompt_org_key_version"),
        )
        op.create_index("ix_prompt_templates_organization_id", "prompt_templates",
                        ["organization_id"])
        op.create_index("ix_prompt_templates_key", "prompt_templates", ["key"])

    # --- mcp_servers --------------------------------------------------------
    if not _has_table(insp, "mcp_servers"):
        op.create_table(
            "mcp_servers",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("url", sa.String(length=500), nullable=False),
            sa.Column("transport", sa.String(length=20), nullable=False, server_default="http"),
            sa.Column("auth_token", sa.String(length=500), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("discovered_tools", sa.JSON(), nullable=True),
            sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("organization_id", "name", name="uq_mcp_org_name"),
        )
        op.create_index("ix_mcp_servers_organization_id", "mcp_servers", ["organization_id"])

    # --- ai_agent_runs ------------------------------------------------------
    if not _has_table(insp, "ai_agent_runs"):
        op.create_table(
            "ai_agent_runs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("agent_key", sa.String(length=120), nullable=False),
            sa.Column("goal", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("plan", sa.JSON(), nullable=True),
            sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("checkpoints", sa.JSON(), nullable=True),
            sa.Column("result", sa.JSON(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("pending_approval", sa.JSON(), nullable=True),
            sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_ai_agent_runs_organization_id", "ai_agent_runs", ["organization_id"])
        op.create_index("ix_ai_agent_runs_status", "ai_agent_runs", ["status"])

    # --- ai_memory_entries --------------------------------------------------
    if not _has_table(insp, "ai_memory_entries"):
        op.create_table(
            "ai_memory_entries",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("scope", sa.String(length=20), nullable=False, server_default="semantic"),
            sa.Column("namespace", sa.String(length=120), nullable=False, server_default="default"),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("embedding", sa.JSON(), nullable=True),
            sa.Column("embedding_provider", sa.String(length=40), nullable=True),
            sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"),
            sa.Column("entry_metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_ai_memory_entries_organization_id", "ai_memory_entries",
                        ["organization_id"])
        op.create_index("ix_ai_memory_entries_user_id", "ai_memory_entries", ["user_id"])
        op.create_index("ix_ai_memory_entries_scope", "ai_memory_entries", ["scope"])
        op.create_index("ix_ai_memory_entries_namespace", "ai_memory_entries", ["namespace"])

    # --- ai_evaluations -----------------------------------------------------
    if not _has_table(insp, "ai_evaluations"):
        op.create_table(
            "ai_evaluations",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=True),
            sa.Column("feature", sa.String(length=80), nullable=False),
            sa.Column("provider", sa.String(length=40), nullable=True),
            sa.Column("model", sa.String(length=120), nullable=True),
            sa.Column("hallucination_risk", sa.Float(), nullable=False, server_default="0"),
            sa.Column("grounding_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("answer_quality", sa.Float(), nullable=False, server_default="0"),
            sa.Column("tool_success", sa.Float(), nullable=False, server_default="0"),
            sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0"),
            sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
            sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_ai_evaluations_organization_id", "ai_evaluations",
                        ["organization_id"])
        op.create_index("ix_ai_evaluations_feature", "ai_evaluations", ["feature"])

    # --- ai_usage_records ---------------------------------------------------
    if not _has_table(insp, "ai_usage_records"):
        op.create_table(
            "ai_usage_records",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=True),
            sa.Column("feature", sa.String(length=80), nullable=False),
            sa.Column("provider", sa.String(length=40), nullable=False),
            sa.Column("model", sa.String(length=120), nullable=False),
            sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
            sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0"),
            sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="success"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_ai_usage_records_organization_id", "ai_usage_records",
                        ["organization_id"])
        op.create_index("ix_ai_usage_records_feature", "ai_usage_records", ["feature"])
        op.create_index("ix_ai_usage_records_provider", "ai_usage_records", ["provider"])


def downgrade() -> None:
    for table in (
        "ai_usage_records",
        "ai_evaluations",
        "ai_memory_entries",
        "ai_agent_runs",
        "mcp_servers",
        "prompt_templates",
        "ai_provider_configs",
    ):
        op.drop_table(table)
