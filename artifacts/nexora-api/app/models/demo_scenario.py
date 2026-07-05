"""Sprint 52C.1 — Demo Scenario Engine models.

Two tables:

* ``DemoScenario``   — catalogue entry for a named scenario (5 built-in + custom).
  Belongs to an org; stores the flow spec as JSON.
* ``DemoScenarioRun`` — one execution / replay of a scenario.  Captures the
  generated events and a step-by-step timeline so replay is deterministic.

Safety invariants (inherited from Sprint 52C):
* No real credentials created.  No cloud access.  No production integrations.
* Strictly additive — new tables only.
"""

from __future__ import annotations

import enum

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class ScenarioType(str, enum.Enum):
    CHECKOUT_OUTAGE = "CHECKOUT_OUTAGE"
    DATABASE_LATENCY = "DATABASE_LATENCY"
    MEMORY_LEAK = "MEMORY_LEAK"
    BAD_DEPLOYMENT = "BAD_DEPLOYMENT"
    COST_EXPLOSION = "COST_EXPLOSION"
    CUSTOM = "CUSTOM"


class ScenarioStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ScenarioRunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DemoScenario(Base, UUIDMixin, TimestampMixin):
    """Catalogue entry for a demo scenario (one per org per scenario type)."""

    __tablename__ = "demo_scenarios"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    scenario_type: Mapped[str] = mapped_column(
        String(40), nullable=False, index=True,
        default=ScenarioType.CUSTOM.value,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON list of {step_number, name, description, system, action}
    flow_steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Which demo org template this scenario targets (e.g. "ecommerce")
    template_key: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ScenarioStatus.AVAILABLE.value,
    )
    run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )


class DemoScenarioRun(Base, UUIDMixin, TimestampMixin):
    """One execution (or replay) of a DemoScenario."""

    __tablename__ = "demo_scenario_runs"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    scenario_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("demo_scenarios.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # If this run is a replay, point back to the original.
    replayed_from_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("demo_scenario_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_replay: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ScenarioRunStatus.PENDING.value,
    )
    # JSON list of generated event IDs/summaries produced during this run.
    generated_events: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Ordered step-execution log: [{step, status, summary, timestamp_iso}]
    step_log: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # IDs of incident/alert rows generated (for linking to timeline)
    incident_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    alert_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
