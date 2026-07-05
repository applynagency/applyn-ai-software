"""AI Platform models (Sprint 61D).

Persistence for the unified AI runtime:

* ``ai_provider_configs`` — per-org routing policy + enabled providers/keys ref
* ``prompt_templates``    — versioned prompt registry (global + org overrides)
* ``mcp_servers``         — org-registered MCP servers (remote tools)
* ``ai_agent_runs``       — agent runtime state (plan/checkpoints/approval/resume)
* ``ai_memory_entries``   — semantic/episodic/org/user long-term memory
* ``ai_evaluations``      — historical AI evaluations
* ``ai_usage_records``    — token + cost accounting per org/feature/provider/model
"""

from __future__ import annotations

import enum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDMixin


class MemoryScope(str, enum.Enum):
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    ORGANIZATION = "organization"
    USER = "user"


class AIAgentRunStatus(str, enum.Enum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AIProviderConfig(Base, UUIDMixin, TimestampMixin):
    """Per-org AI routing configuration (one row per org)."""

    __tablename__ = "ai_provider_configs"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    routing_policy: Mapped[str] = mapped_column(String(30), nullable=False, default="highest_quality")
    # Enabled provider names; null/empty => all known providers.
    enabled_providers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Ordered [[provider, model], ...] used when routing_policy == custom.
    preferred_models: Mapped[list | None] = mapped_column(JSON, nullable=True)
    default_temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
    default_max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=1024)
    cache_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class PromptTemplate(Base, UUIDMixin, TimestampMixin):
    """A versioned prompt. ``organization_id`` null => global; non-null => override."""

    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", "version", name="uq_prompt_org_key_version"),
    )

    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    # Declared variable names for validation/testing.
    variables: Mapped[list | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class MCPServer(Base, UUIDMixin, TimestampMixin):
    """An organization-registered Model Context Protocol server (remote tools)."""

    __tablename__ = "mcp_servers"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_mcp_org_name"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    transport: Mapped[str] = mapped_column(String(20), nullable=False, default="http")
    auth_token: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Cached tool catalog from the last successful discovery.
    discovered_tools: Mapped[list | None] = mapped_column(JSON, nullable=True)
    last_synced_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AIAgentRun(Base, UUIDMixin, TimestampMixin):
    """Agent-runtime state with checkpoints for resume + approval gating."""

    __tablename__ = "ai_agent_runs"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    agent_key: Mapped[str] = mapped_column(String(120), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=AIAgentRunStatus.PENDING.value, index=True)
    plan: Mapped[list | None] = mapped_column(JSON, nullable=True)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Ordered list of checkpoint dicts {step, state, output, ts} for resume.
    checkpoints: Mapped[list | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pending_approval: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class AIMemoryEntry(Base, UUIDMixin, TimestampMixin):
    """A long-term memory record (semantic/episodic/org/user)."""

    __tablename__ = "ai_memory_entries"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default=MemoryScope.SEMANTIC.value, index=True)
    namespace: Mapped[str] = mapped_column(String(120), nullable=False, default="default", index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Embedding vector for semantic recall (provider-independent JSON list).
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    embedding_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    entry_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class AIEvaluation(Base, UUIDMixin, TimestampMixin):
    """A stored AI evaluation result (historical reporting)."""

    __tablename__ = "ai_evaluations"

    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    feature: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    hallucination_risk: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    grounding_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    answer_quality: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tool_success: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class AIUsageRecord(Base, UUIDMixin, TimestampMixin):
    """One row per AI gateway call for cost/token accounting per org & feature."""

    __tablename__ = "ai_usage_records"

    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    feature: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
