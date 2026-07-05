"""Sprint 42A — Continuous Monitoring & Auto Incident Creation schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class NormalizedAlertInput(BaseModel):
    """A normalized alert pushed into the monitoring engine (manual trigger /
    tests / provider adapters). Carries only customer-safe metadata."""

    provider: str = Field(min_length=1, max_length=40)
    alert_id: str = Field(min_length=1, max_length=200)
    alert_name: str = Field(min_length=1, max_length=255)
    severity: str = Field(default="WARNING", max_length=20)
    status: str = Field(default="FIRING", max_length=20)
    service: str | None = Field(default=None, max_length=200)
    environment: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    timestamp: datetime | None = None
    # Sprint 58A.3 — richer normalized fields (optional; backward compatible).
    resource: str | None = Field(default=None, max_length=512)
    region: str | None = Field(default=None, max_length=120)
    labels: dict = Field(default_factory=dict)
    annotations: dict = Field(default_factory=dict)
    correlation_id: str | None = Field(default=None, max_length=64)


class MonitoringAlertResponse(BaseModel):
    id: str
    organization_id: str
    provider: str
    alert_id: str
    alert_name: str
    severity: str
    status: str
    service: str | None = None
    environment: str | None = None
    description: str | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    occurrence_count: int
    incident_id: str | None = None
    resource: str | None = None
    region: str | None = None
    labels: dict = Field(default_factory=dict)
    annotations: dict = Field(default_factory=dict)
    correlation_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("labels", "annotations", mode="before")
    @classmethod
    def _none_to_dict(cls, v):
        return v or {}


class MonitoringAlertInvestigateResponse(BaseModel):
    alert_id: str
    incident_id: str | None = None
    created: bool = False
    investigated: bool = False
    message: str | None = None


class MonitoringAlertListResponse(BaseModel):
    items: list[MonitoringAlertResponse]
    total: int


class MonitoringPollRequest(BaseModel):
    """Manual/admin trigger of the polling cycle.

    Optionally restrict to specific providers, and/or push pre-normalized alerts
    (used by adapters and tests). Read-only — never executes anything.
    """

    providers: list[str] | None = None
    alerts: list[NormalizedAlertInput] | None = None


class IngestionMetrics(BaseModel):
    alerts_received: int = 0
    alerts_processed: int = 0
    failures: int = 0
    latency_ms: int = 0


class MonitoringPollResponse(BaseModel):
    polled_providers: list[str] = []
    alerts_ingested: int = 0
    new_alerts: int = 0
    deduplicated: int = 0
    incidents_created: int = 0
    notifications_sent: int = 0
    alerts: list[MonitoringAlertResponse] = []
    metrics: IngestionMetrics = IngestionMetrics()


class MonitoringWebhookRequest(BaseModel):
    """Push-based ingestion of a provider alert payload (org-scoped)."""

    provider: str = Field(min_length=1, max_length=40)
    payload: dict = Field(default_factory=dict)


class DeadLetterResponse(BaseModel):
    id: str
    provider: str
    source: str
    status: str
    error: str | None = None
    attempts: int = 1
    payload_digest: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TrendPoint(BaseModel):
    period: str
    count: int = 0


class ServiceCount(BaseModel):
    service: str
    count: int = 0


class RecentRemediation(BaseModel):
    id: str
    investigation_id: str
    title: str
    provider: str
    status: str
    risk_level: str
    created_at: datetime


class CurrentOnCallEntry(BaseModel):
    schedule_id: str
    schedule_name: str
    team: str | None = None
    user_id: str | None = None


class MonitoringDashboardResponse(BaseModel):
    """Operations Center summary."""

    active_alerts: int = 0
    open_incidents: int = 0
    critical_incidents: int = 0
    mttr_minutes: float | None = None
    total_incidents: int = 0
    incident_trend: list[TrendPoint] = []
    top_affected_services: list[ServiceCount] = []
    recent_remediations: list[RecentRemediation] = []
    recent_alerts: list[MonitoringAlertResponse] = []
    # Sprint 42B — on-call & escalation.
    unacknowledged_incidents: int = 0
    escalated_incidents: int = 0
    mtta_minutes: float | None = None
    current_oncall: list[CurrentOnCallEntry] = []
    # Sprint 58A.3 — ingestion health.
    dead_letters: int = 0
