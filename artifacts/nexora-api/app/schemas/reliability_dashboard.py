"""Sprint 45B - Executive Reliability Dashboard schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ScoreComponent(BaseModel):
    name: str
    score: float            # 0-100 sub-score for this dimension
    weight: float           # contribution weight (0-1)
    points: float           # weighted points contributed to the final score
    detail: str


class RiskService(BaseModel):
    service: str
    score: float            # failure probability or 100-health
    basis: str              # "change_failure_prediction" | "service_health"


class DashboardMetrics(BaseModel):
    # Availability / SLO
    availability_30d: float | None = None
    slo_compliance_percentage: float | None = None
    error_budget_remaining_percentage: float | None = None
    services_total: int = 0
    services_at_risk: int = 0
    # Incident response
    mtta_minutes: float | None = None
    mttr_minutes: float | None = None
    total_incidents: int = 0
    open_incidents: int = 0
    # Deployments
    total_deployments: int = 0
    deployment_success_rate: float | None = None
    rollback_rate: float | None = None
    # Capacity
    capacity_resources: int = 0
    capacity_at_risk: int = 0
    # Cost
    monthly_cost: float | None = None
    potential_savings: float | None = None
    # Blast radius
    largest_blast_radius: int = 0
    largest_blast_radius_service: str | None = None
    # Highest risk
    highest_risk_services: list[RiskService] = []


class TrendBucket(BaseModel):
    period_start: str
    incidents: int = 0
    deployments: int = 0
    failed_deployments: int = 0
    deployment_success_rate: float | None = None
    cost: float | None = None
    capacity_at_risk: int = 0
    max_blast_radius: int = 0


class TrendSeries(BaseModel):
    window_days: int
    bucket_days: int
    buckets: list[TrendBucket] = []


class ReliabilityDashboardResponse(BaseModel):
    scope: str                       # organization | team | service
    scope_value: str | None = None
    window_days: int
    reliability_score: int
    score_grade: str
    score_breakdown: list[ScoreComponent] = []
    metrics: DashboardMetrics
    trends_7d: TrendSeries
    trends_30d: TrendSeries
    trends_90d: TrendSeries
    generated_at: datetime


class ExecutiveSummaryResponse(BaseModel):
    scope: str
    scope_value: str | None = None
    reliability_score: int
    score_grade: str
    summary: str
    highlights: list[str] = []
    risks: list[str] = []
    recommendations: list[str] = []
    generated_at: datetime
