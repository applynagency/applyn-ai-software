"""Sprint 42B — On-Call & Escalation schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ------------------------------------------------------------- service owners
class ServiceOwnerCreate(BaseModel):
    service_name: str = Field(min_length=1, max_length=200)
    primary_owner_id: str | None = None
    secondary_owner_id: str | None = None
    team: str | None = Field(default=None, max_length=120)
    escalation_group: str | None = Field(default=None, max_length=120)


class ServiceOwnerUpdate(BaseModel):
    primary_owner_id: str | None = None
    secondary_owner_id: str | None = None
    team: str | None = Field(default=None, max_length=120)
    escalation_group: str | None = Field(default=None, max_length=120)


class ServiceOwnerResponse(BaseModel):
    id: str
    organization_id: str
    service_name: str
    primary_owner_id: str | None = None
    secondary_owner_id: str | None = None
    team: str | None = None
    escalation_group: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --------------------------------------------------------------- on-call schedules
class OnCallScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    team: str | None = Field(default=None, max_length=120)
    rotation_type: str = Field(default="WEEKLY", max_length=20)
    timezone: str = Field(default="UTC", max_length=60)
    participants: list[str] = Field(default_factory=list)
    anchor_at: datetime | None = None
    is_active: bool = True


class OnCallScheduleResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    team: str | None = None
    rotation_type: str
    timezone: str
    participants: list[str] = []
    anchor_at: datetime
    is_active: bool
    current_oncall_user_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------- escalation policies
class EscalationStepInput(BaseModel):
    after_minutes: int = Field(ge=0)
    target_type: str = Field(max_length=30)
    target_user_id: str | None = None
    channels: str = Field(default="slack,email", max_length=40)


class EscalationStepResponse(BaseModel):
    id: str
    step_order: int
    after_minutes: int
    target_type: str
    target_user_id: str | None = None
    channels: str

    model_config = {"from_attributes": True}


class EscalationPolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    service_name: str | None = Field(default=None, max_length=200)
    is_active: bool = True
    steps: list[EscalationStepInput] = Field(default_factory=list)


class EscalationPolicyResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    service_name: str | None = None
    is_active: bool
    steps: list[EscalationStepResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


# --------------------------------------------------------------- assignments
class IncidentAssignmentResponse(BaseModel):
    id: str
    organization_id: str
    incident_id: str
    service_name: str | None = None
    owner_id: str | None = None
    responder_id: str | None = None
    approver_id: str | None = None
    oncall_schedule_id: str | None = None
    escalation_policy_id: str | None = None
    state: str
    current_level: int
    assigned_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by_id: str | None = None
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}


class EscalationEventResponse(BaseModel):
    id: str
    incident_id: str
    assignment_id: str
    level: int
    after_minutes: int
    target_type: str
    target_user_id: str | None = None
    channels: str | None = None
    reason: str | None = None
    notified_at: datetime

    model_config = {"from_attributes": True}


class IncidentAssignmentDetailResponse(IncidentAssignmentResponse):
    escalations: list[EscalationEventResponse] = []


class AcknowledgeRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class StateUpdateRequest(BaseModel):
    state: str = Field(max_length=20)


# --------------------------------------------------------------- MTTA / metrics
class MetricBreakdown(BaseModel):
    key: str
    mtta_minutes: float | None = None
    mttr_minutes: float | None = None
    incidents: int = 0
    acknowledged: int = 0


class MTTAResponse(BaseModel):
    organization_mtta_minutes: float | None = None
    organization_mttr_minutes: float | None = None
    total_incidents: int = 0
    acknowledged_incidents: int = 0
    by_service: list[MetricBreakdown] = []
    by_team: list[MetricBreakdown] = []


class CurrentOnCall(BaseModel):
    schedule_id: str
    schedule_name: str
    team: str | None = None
    user_id: str | None = None
