"""Pydantic schemas for Enterprise Incident Response Platform API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ScheduleOverrideCreate(BaseModel):
    schedule_id: str
    replacement_user_id: str
    starts_at: datetime
    ends_at: datetime
    reason: str | None = None


class ScheduleOverrideView(BaseModel):
    id: str
    schedule_id: str
    replacement_user_id: str
    starts_at: datetime
    ends_at: datetime
    reason: str | None

    model_config = {"from_attributes": True}


class OncallDashboardView(BaseModel):
    schedules: list
    current_oncall: list
    overrides: list
    shift_timeline: list


class EscalationRunRequest(BaseModel):
    incident_id: str | None = None


class EscalationDashboardView(BaseModel):
    policies: list
    recent_events: list
    channels_supported: list


class StatusPageCreate(BaseModel):
    name: str
    slug: str
    visibility: str = "PUBLIC"
    branding: dict = Field(default_factory=dict)


class StatusPageView(BaseModel):
    id: str
    name: str
    slug: str
    visibility: str
    branding: dict
    is_active: bool

    model_config = {"from_attributes": True}


class StatusComponentCreate(BaseModel):
    name: str
    description: str | None = None
    status: str = "OPERATIONAL"
    position: int = 0


class StatusComponentView(BaseModel):
    id: str
    name: str
    description: str | None
    status: str
    position: int

    model_config = {"from_attributes": True}


class StatusIncidentCreate(BaseModel):
    title: str
    impact: str | None = None
    incident_id: str | None = None


class CommunicationTemplateCreate(BaseModel):
    name: str
    kind: str
    subject: str
    body: str
    locale: str = "en"
    requires_approval: bool = False


class CommunicationCreate(BaseModel):
    incident_id: str | None = None
    template_key: str | None = None
    kind: str = "INTERNAL"
    subject: str | None = None
    body: str | None = None
    context: dict = Field(default_factory=dict)
    scheduled_at: datetime | None = None


class CommunicationView(BaseModel):
    id: str
    incident_id: str | None
    kind: str
    subject: str
    body: str
    status: str
    scheduled_at: datetime | None
    sent_at: datetime | None

    model_config = {"from_attributes": True}


class MajorIncidentCreate(BaseModel):
    incident_id: str
    executive_bridge: bool = False
    roles: dict = Field(default_factory=dict)
    stakeholders: list = Field(default_factory=list)


class MajorIncidentView(BaseModel):
    id: str
    incident_id: str
    war_room_id: str | None
    roles: dict
    stakeholders: list
    decision_log: list
    executive_bridge: bool
    status: str
    started_at: datetime

    model_config = {"from_attributes": True}


class CoordinatorRequest(BaseModel):
    incident_id: str | None = None


class AnalyticsView(BaseModel):
    mtta_minutes: float | None
    mttr_minutes: float | None
    open_incidents: int
    escalation_success_rate: float | None
    responder_workload: list
    incident_trend: list
    by_severity: dict
    by_service: dict
    top_root_causes: list
    action_item_completion_rate: float | None


class PostmortemPlatformView(BaseModel):
    postmortems: list
    pending_count: int
    completed_count: int
