"""Sprint 46C - Executive Reliability Reporting Engine.

Persisted, period-scoped executive reports (weekly / monthly / quarterly) that
roll up the platform's reliability intelligence into a board-ready document:
incident summary, availability, MTTR/MTTA, SLO compliance, deployment success,
cost savings, capacity forecast and the composite Reliability Score - plus a
trend comparison against the previous report of the same cadence, an executive
summary, and an auto-generated action plan.

Read-only over existing signals: generation reads and aggregates, it never
mutates incidents, deployments, SLOs, or any source data.
"""

import enum

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, DateTime

from app.database.base import Base, TimestampMixin, UUIDMixin


class ReportPeriod(str, enum.Enum):
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"


class ExecutiveReport(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "executive_reports"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ReportPeriod.MONTHLY.value, index=True
    )
    period_start: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), nullable=False)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    reliability_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score_grade: Mapped[str] = mapped_column(String(2), nullable=False, default="F")
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trend: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    executive_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_plan: Mapped[list | None] = mapped_column(JSON, nullable=True)
    highlights: Mapped[list | None] = mapped_column(JSON, nullable=True)
    risks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    content_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
