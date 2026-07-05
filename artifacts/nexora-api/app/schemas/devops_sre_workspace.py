"""Pydantic schemas for the DevOps & SRE workspace API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class QueueItemView(BaseModel):
    id: str
    type: str
    title: str
    owner: str | None = None
    priority: str
    status: str
    age_minutes: int
    sla_minutes: int | None = None
    suggested_action: str
    reference_type: str | None = None
    reference_id: str | None = None
    meta: dict = Field(default_factory=dict)


class MyWorkSection(BaseModel):
    key: str
    label: str
    count: int
    priority: str
    items: list[dict] = Field(default_factory=list)


class MyWorkDashboardView(BaseModel):
    sections: list[MyWorkSection]
    total_attention_items: int
    updated_at: datetime


class OperationsQueueView(BaseModel):
    items: list[QueueItemView]
    total: int


class ChangeEventView(BaseModel):
    id: str
    kind: str
    title: str
    actor: str | None = None
    status: str | None = None
    occurred_at: datetime
    reference_type: str | None = None
    reference_id: str | None = None
    meta: dict = Field(default_factory=dict)


class ChangeCenterView(BaseModel):
    events: list[ChangeEventView]
    total: int


class MaintenanceCreate(BaseModel):
    kind: str = "WINDOW"
    title: str
    description: str | None = None
    starts_at: datetime
    ends_at: datetime
    impact_summary: str | None = None
    cluster_id: str | None = None
    environment_id: str | None = None
    requires_approval: bool = True


class MaintenanceView(BaseModel):
    id: str
    kind: str
    title: str
    description: str | None = None
    status: str
    starts_at: datetime
    ends_at: datetime
    impact_summary: str | None = None
    cluster_id: str | None = None
    environment_id: str | None = None
    requires_approval: bool
    approved_by: str | None = None
    created_by: str

    model_config = {"from_attributes": True}


class MaintenanceCenterView(BaseModel):
    windows: list[MaintenanceView]
    upcoming: list[MaintenanceView]
    active_freezes: list[MaintenanceView]


class CalendarEventView(BaseModel):
    id: str
    kind: str
    title: str
    starts_at: datetime
    ends_at: datetime | None = None
    reference_type: str | None = None
    reference_id: str | None = None
    meta: dict | None = None

    model_config = {"from_attributes": True}


class SLOCenterView(BaseModel):
    slis: list[dict] = Field(default_factory=list)
    slos: list[dict] = Field(default_factory=list)
    error_budgets: list[dict] = Field(default_factory=list)
    burn_rates: list[dict] = Field(default_factory=list)
    predictions: list[dict] = Field(default_factory=list)
    ai_recommendations: list[dict] = Field(default_factory=list)
    linked_incidents: list[dict] = Field(default_factory=list)
    linked_deployments: list[dict] = Field(default_factory=list)


class CostOperationsView(BaseModel):
    has_data: bool = False
    daily_spend: float | None = None
    namespace_spend: list[dict] = Field(default_factory=list)
    cluster_spend: list[dict] = Field(default_factory=list)
    idle_resources: int = 0
    waste_estimate: float | None = None
    rightsizing: list[dict] = Field(default_factory=list)
    recommendations: list[dict] = Field(default_factory=list)
    projected_monthly_bill: float | None = None


class ExecutiveView(BaseModel):
    platform_health_score: float | None = None
    deployment_success_rate: float | None = None
    availability: float | None = None
    mttr_hours: float | None = None
    mttd_hours: float | None = None
    dora: dict = Field(default_factory=dict)
    top_incidents: list[dict] = Field(default_factory=list)
    top_risks: list[dict] = Field(default_factory=list)
    monthly_trend: list[dict] = Field(default_factory=list)
    business_impact: str | None = None


class BriefingView(BaseModel):
    id: str
    briefing_date: str
    summary: str
    sections: dict
    recommended_actions: list
    created_at: datetime

    model_config = {"from_attributes": True}


class HandoverView(BaseModel):
    id: str
    title: str
    markdown: str
    sections: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class AutomationSuggestionView(BaseModel):
    id: str
    kind: str
    title: str
    pattern: str
    occurrence_count: int
    recommendation: str
    evidence: dict
    dismissed: bool
    accepted: bool

    model_config = {"from_attributes": True}


class OperationalKPIsView(BaseModel):
    mttr_hours: float | None = None
    mttd_hours: float | None = None
    mtta_hours: float | None = None
    availability_percent: float | None = None
    deployment_frequency_per_day: float | None = None
    lead_time_hours: float | None = None
    change_failure_rate_percent: float | None = None
    error_budget_burn_rate: float | None = None
    incident_recurrence_rate: float | None = None
    automation_success_rate: float | None = None
    approval_time_hours: float | None = None
    ai_recommendation_acceptance_rate: float | None = None
    window_days: int = 30


class AIContextRequest(BaseModel):
    page: str | None = None
    reference_type: str | None = None
    reference_id: str | None = None
    question: str | None = None


class AIContextView(BaseModel):
    context: dict
    suggested_questions: list[str] = Field(default_factory=list)
    copilot_endpoint: str = "/v1/copilot/chat"
