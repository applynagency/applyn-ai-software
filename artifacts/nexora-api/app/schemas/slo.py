"""Sprint 42C — Service Health & SLO Intelligence schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ catalog
class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    owner_team: str | None = Field(default=None, max_length=120)
    tier: str = Field(default="TIER_2", max_length=20)


class ServiceUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    owner_team: str | None = Field(default=None, max_length=120)
    tier: str | None = Field(default=None, max_length=20)


class ServiceResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    description: str | None = None
    owner_team: str | None = None
    tier: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------- slos
class ServiceSLOCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slo_type: str = Field(default="AVAILABILITY", max_length=20)
    target_percentage: float = Field(default=99.9, gt=0, le=100)
    window_days: int = Field(default=30, ge=1, le=365)
    latency_percentile: str | None = Field(default=None, max_length=10)
    threshold_ms: float | None = Field(default=None, ge=0)


class ServiceSLOResponse(BaseModel):
    id: str
    organization_id: str
    service_id: str
    name: str
    slo_type: str
    target_percentage: float
    window_days: int
    latency_percentile: str | None = None
    threshold_ms: float | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------ health report
class AvailabilityWindow(BaseModel):
    window: str  # "24h" / "7d" / "30d"
    availability_percentage: float
    downtime_minutes: float


class ErrorBudget(BaseModel):
    target_percentage: float
    window_days: int
    allowed_downtime_minutes: float
    consumed_minutes: float
    remaining_minutes: float
    remaining_percentage: float | None = None


class BurnRate(BaseModel):
    burn_rate: float
    status: str  # NORMAL / WARNING / CRITICAL
    downtime_last_24h_minutes: float
    description: str | None = None


class SLOComplianceItem(BaseModel):
    slo_id: str
    name: str
    slo_type: str
    target_percentage: float
    window_days: int
    observed_value: float | None = None
    compliant: bool | None = None
    status: str  # HEALTHY / AT_RISK / BREACHED / NO_DATA
    latency_percentile: str | None = None
    threshold_ms: float | None = None
    p50_ms: float | None = None
    p95_ms: float | None = None
    p99_ms: float | None = None


class SLOPrediction(BaseModel):
    will_breach: bool = False
    days_to_exhaustion: float | None = None
    projected_exhaustion_at: datetime | None = None
    message: str


class CorrelatedIncident(BaseModel):
    incident_id: str
    title: str
    severity: str | None = None
    status: str
    downtime_minutes: float
    created_at: datetime


class CorrelatedAlert(BaseModel):
    id: str
    alert_name: str
    severity: str
    occurrence_count: int
    last_seen_at: datetime


class CorrelatedDeployment(BaseModel):
    id: str
    status: str
    environment: str
    created_at: datetime


class ServiceHealthReport(BaseModel):
    service_id: str
    name: str
    tier: str
    owner_team: str | None = None
    health_score: int
    availability: list[AvailabilityWindow] = []
    error_budget: ErrorBudget | None = None
    burn_rate: BurnRate | None = None
    slo_compliance: list[SLOComplianceItem] = []
    prediction: SLOPrediction | None = None
    open_incidents: int = 0
    mtta_minutes: float | None = None
    mttr_minutes: float | None = None
    correlated_incidents: list[CorrelatedIncident] = []
    correlated_alerts: list[CorrelatedAlert] = []
    correlated_deployments: list[CorrelatedDeployment] = []


class ServiceHealthSummary(BaseModel):
    service_id: str
    name: str
    tier: str
    owner_team: str | None = None
    health_score: int
    availability_30d: float
    error_budget_remaining_percentage: float | None = None
    burn_rate: float
    burn_status: str
    open_incidents: int


class ServiceHealthOverview(BaseModel):
    services: list[ServiceHealthSummary] = []
    average_health_score: int | None = None
    services_at_risk: int = 0
