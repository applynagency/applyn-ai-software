"""Sprint 46A - Reliability Maturity Score Engine schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CategoryScore(BaseModel):
    category: str
    score: int
    maturity_level: str
    weight: float
    detail: str
    signals: dict = {}


class Recommendation(BaseModel):
    category: str
    priority: str            # HIGH | MEDIUM | LOW
    recommendation: str
    impact: float            # estimated overall-score points recoverable


class AssessmentResponse(BaseModel):
    id: str
    organization_id: str
    overall_score: int
    maturity_level: str
    summary: str | None = None
    strengths: list[str] = []
    weaknesses: list[str] = []
    recommendations: list[Recommendation] = []
    categories: list[CategoryScore] = []
    details: dict = {}
    created_at: datetime

    model_config = {"from_attributes": True}


class AssessmentSummary(BaseModel):
    id: str
    overall_score: int
    maturity_level: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TrendPoint(BaseModel):
    date: str
    overall_score: int
    maturity_level: str


class CategoryTrend(BaseModel):
    category: str
    points: list[int] = []


class ReliabilityDashboard(BaseModel):
    latest: AssessmentResponse | None = None
    assessments_count: int = 0
    trend: list[TrendPoint] = []
    category_trends: list[CategoryTrend] = []


class AnalyzeRequest(BaseModel):
    # No inputs required; the engine reads existing org-scoped intelligence.
    note: str | None = None
