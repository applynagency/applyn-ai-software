"""Sprint 43B — Cost Optimization Intelligence schemas (read-only, advisory)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CostAnalyzeRequest(BaseModel):
    cluster: str | None = Field(default=None, max_length=120)
    service: str | None = Field(default=None, max_length=200)
    environment: str | None = Field(default=None, max_length=50)
    lookback_days: int = Field(default=30, ge=1, le=365)


class CostRecommendation(BaseModel):
    kind: str
    resource_type: str
    scope: str
    title: str
    detail: str
    current_cost: float
    projected_cost: float
    monthly_savings: float
    action: str


class CostTrendPoint(BaseModel):
    period: str
    cost: float
    anomaly: bool = False


class NameCost(BaseModel):
    name: str
    cost: float


class CostReport(BaseModel):
    id: str
    organization_id: str
    cluster: str | None = None
    service: str | None = None
    environment: str | None = None

    current_cost: float
    estimated_waste: float
    potential_savings: float
    optimized_cost: float
    annual_savings: float
    savings_percentage: float

    optimization_score: int
    optimization_level: str

    forecast_30d: float
    forecast_90d: float
    forecast_365d: float

    idle_count: int
    overprovisioned_count: int
    nonprod_count: int

    confidence: float
    created_at: datetime

    recommendations: list[CostRecommendation] = []
    weekly_trend: list[CostTrendPoint] = []
    monthly_trend: list[CostTrendPoint] = []
    cost_by_service: list[NameCost] = []
    cost_by_environment: list[NameCost] = []

    model_config = {"from_attributes": True}


class CostAnalysisSummary(BaseModel):
    id: str
    organization_id: str
    cluster: str | None = None
    service: str | None = None
    environment: str | None = None
    current_cost: float
    estimated_waste: float
    potential_savings: float
    annual_savings: float
    optimization_score: int
    optimization_level: str
    idle_count: int
    overprovisioned_count: int
    nonprod_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CostAnalysisListResponse(BaseModel):
    items: list[CostAnalysisSummary] = []
    total: int = 0
    offset: int = 0
    limit: int = 50


class CostDashboard(BaseModel):
    has_data: bool = False
    current_cost: float = 0.0
    forecast_30d: float = 0.0
    forecast_90d: float = 0.0
    forecast_365d: float = 0.0
    estimated_waste: float = 0.0
    potential_savings: float = 0.0
    annual_savings: float = 0.0
    optimized_cost: float = 0.0
    savings_percentage: float = 0.0
    optimization_score: int = 100
    optimization_level: str = "EXCELLENT"
    idle_count: int = 0
    overprovisioned_count: int = 0
    nonprod_count: int = 0
    analyzed_at: datetime | None = None
    top_recommendations: list[CostRecommendation] = []
    weekly_trend: list[CostTrendPoint] = []
    cost_by_service: list[NameCost] = []
    cost_by_environment: list[NameCost] = []
