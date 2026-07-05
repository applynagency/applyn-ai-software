"""Sprint 43A — Capacity Planning & Forecasting schemas (read-only)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ----------------------------------------------------------------- collection
class CapacityMetricInput(BaseModel):
    resource_type: str = Field(max_length=20)
    usage: float = Field(ge=0)
    capacity: float = Field(gt=0)
    cluster: str | None = Field(default=None, max_length=120)
    service: str | None = Field(default=None, max_length=200)
    environment: str | None = Field(default=None, max_length=50)
    unit: str | None = Field(default=None, max_length=20)
    recorded_at: datetime | None = None


class CapacityMetricIngestRequest(BaseModel):
    samples: list[CapacityMetricInput] = Field(min_length=1)


class CapacityMetricIngestResponse(BaseModel):
    ingested: int


# ------------------------------------------------------------------ forecasts
class ForecastCreateRequest(BaseModel):
    resource_type: str | None = Field(default=None, max_length=20)
    cluster: str | None = Field(default=None, max_length=120)
    service: str | None = Field(default=None, max_length=200)
    environment: str | None = Field(default=None, max_length=50)
    saturation_threshold: float = Field(default=90.0, gt=0, le=100)
    lookback_days: int = Field(default=30, ge=1, le=365)


class TrendPoint(BaseModel):
    timestamp: datetime
    utilization: float


class ForecastResponse(BaseModel):
    id: str
    organization_id: str
    cluster: str | None = None
    service: str | None = None
    environment: str | None = None
    resource_type: str
    unit: str | None = None

    current_usage: float
    capacity: float
    current_utilization: float
    growth_rate_per_day: float
    trend: str

    forecast_7d: float
    forecast_30d: float
    forecast_90d: float

    saturation_threshold: float
    saturation_date: datetime | None = None
    exhaustion_date: datetime | None = None
    status: str

    recommendation_action: str
    recommendation: str | None = None

    current_cost: float
    projected_cost: float
    delta_cost: float

    confidence: float
    data_points: int
    trend_points: list[TrendPoint] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class ForecastListResponse(BaseModel):
    items: list[ForecastResponse] = []
    total: int = 0
    offset: int = 0
    limit: int = 50


class ResourceSummary(BaseModel):
    resource_type: str
    status: str
    current_utilization: float
    forecast_30d: float
    exhaustion_date: datetime | None = None
    recommendation_action: str


class CapacityDashboard(BaseModel):
    total_forecasts: int = 0
    critical_count: int = 0
    warning_count: int = 0
    healthy_count: int = 0
    total_current_cost: float = 0.0
    total_projected_cost: float = 0.0
    total_delta_cost: float = 0.0
    soonest_exhaustion_date: datetime | None = None
    by_resource: list[ResourceSummary] = []
    recent_forecasts: list[ForecastResponse] = []
