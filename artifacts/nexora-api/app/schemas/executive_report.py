"""Sprint 46C - Executive Reliability Reporting schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReportGenerateRequest(BaseModel):
    report_type: str = Field(default="MONTHLY")


class ActionItem(BaseModel):
    priority: str          # HIGH | MEDIUM | LOW
    category: str
    action: str
    rationale: str


class MetricDelta(BaseModel):
    metric: str
    current: float | None = None
    previous: float | None = None
    delta: float | None = None
    direction: str = "flat"   # up | down | flat
    improved: bool | None = None


class ReportTrend(BaseModel):
    previous_report_id: str | None = None
    previous_score: int | None = None
    score_delta: int | None = None
    direction: str = "flat"
    deltas: list[MetricDelta] = []
    note: str | None = None


class ExecutiveReportResponse(BaseModel):
    id: str
    organization_id: str
    report_type: str
    period_start: datetime
    period_end: datetime
    window_days: int
    reliability_score: int
    score_grade: str
    metrics: dict = {}
    trend: ReportTrend | None = None
    executive_summary: str | None = None
    action_plan: list[ActionItem] = []
    highlights: list[str] = []
    risks: list[str] = []
    content_markdown: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExecutiveReportSummary(BaseModel):
    id: str
    report_type: str
    period_start: datetime
    period_end: datetime
    reliability_score: int
    score_grade: str
    created_at: datetime

    model_config = {"from_attributes": True}
