"""Sprint 51B - Test Playbook Engine.

Repeatable validation scenarios for every platform module. A ``TestPlaybook``
groups ordered ``TestPlaybookStep`` rows (each with preconditions handled at the
playbook level, an action, an expected result and validation criteria). Each
execution is recorded as a ``TestPlaybookRun`` with per-step pass/fail results,
an aggregate status and a generated report.

Org-isolated. Nothing here executes infrastructure actions - runs record the
outcome of validation steps (manual or supplied by the caller). Strictly
additive.
"""

import enum

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class TestPlaybookCategory(str, enum.Enum):
    MONITORING = "MONITORING"
    INCIDENT_MANAGEMENT = "INCIDENT_MANAGEMENT"
    AI_TEAMS = "AI_TEAMS"
    WORKFLOWS = "WORKFLOWS"
    SLO = "SLO"
    DEPLOYMENT_SAFETY = "DEPLOYMENT_SAFETY"
    CAPACITY_PLANNING = "CAPACITY_PLANNING"
    COST_OPTIMIZATION = "COST_OPTIMIZATION"
    AI_COPILOT = "AI_COPILOT"


class TestPlaybookRunStatus(str, enum.Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class StepResultStatus(str, enum.Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class TestPlaybook(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "test_playbooks"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(
        String(40), nullable=False, default=TestPlaybookCategory.MONITORING.value, index=True
    )
    preconditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_system: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class TestPlaybookStep(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "test_playbook_steps"

    playbook_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_playbooks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)


class TestPlaybookRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "test_playbook_runs"

    playbook_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_playbooks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TestPlaybookRunStatus.PASSED.value, index=True
    )
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pass_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0-100
    # Per-step outcomes: [{step_id, title, status, expected_result, actual_result, notes}]
    results: Mapped[list | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
