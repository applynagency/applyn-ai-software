"""Sprint 58A.4 — schemas for incident lifecycle, collaboration, command center."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.incident import (
    DeploymentChangeEventResponse,
    IncidentRecommendationResponse,
    IncidentResponse,
    IncidentStepResponse,
    IncidentTimelineEventResponse,
    RemediationActionResponse,
)


# --------------------------------------------------------------- requests
class LifecycleTransitionRequest(BaseModel):
    status: str = Field(min_length=1, max_length=20)
    note: str | None = Field(default=None, max_length=2000)


class IncidentNoteRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class IncidentAssignRequest(BaseModel):
    assignee_id: str = Field(min_length=1, max_length=36)
    note: str | None = Field(default=None, max_length=2000)


class IncidentEscalateRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)
    run_escalation: bool = False


class IncidentCommentRequest(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class IncidentTaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    assignee_id: str | None = Field(default=None, max_length=36)


class IncidentTaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, max_length=20)
    assignee_id: str | None = Field(default=None, max_length=36)


# --------------------------------------------------------------- responses
class LifecycleEventResponse(BaseModel):
    id: str
    incident_id: str
    event_type: str
    actor_id: str | None = None
    from_status: str | None = None
    to_status: str | None = None
    message: str | None = None
    metadata: dict | None = Field(default=None, validation_alias="event_metadata")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class IncidentCommentResponse(BaseModel):
    id: str
    incident_id: str
    author_id: str | None = None
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentTaskResponse(BaseModel):
    id: str
    incident_id: str
    title: str
    description: str | None = None
    status: str
    assignee_id: str | None = None
    created_by: str | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentAssignmentView(BaseModel):
    """Flattened on-call assignment for the command center (subset)."""

    state: str | None = None
    service_name: str | None = None
    owner_id: str | None = None
    responder_id: str | None = None
    approver_id: str | None = None
    current_level: int = 0
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None


class WarRoomView(BaseModel):
    id: str
    status: str
    title: str
    confidence_score: int | None = None
    message_count: int = 0


class PostmortemView(BaseModel):
    id: str
    status: str
    title: str | None = None
    version: int = 1
    generated_by: str | None = None


class BusinessImpactView(BaseModel):
    severity: str | None = None
    affected_service: str | None = None
    blast_radius: int = 0
    open_minutes: int | None = None
    customer_facing: bool = False


class CommandCenterResponse(BaseModel):
    """Sprint 58A.4 — the unified incident command center payload."""

    incident: IncidentResponse
    available_transitions: list[str] = []
    assignment: IncidentAssignmentView | None = None
    lifecycle_events: list[LifecycleEventResponse] = []
    # AI findings + read-only intelligence
    ai_findings: list[str] = []
    timeline: list[IncidentTimelineEventResponse] = []
    related_changes: list[DeploymentChangeEventResponse] = []
    recommendations: list[IncidentRecommendationResponse] = []
    # Commands (approval-gated remediation actions)
    remediation_actions: list[RemediationActionResponse] = []
    # Human collaboration
    comments: list[IncidentCommentResponse] = []
    tasks: list[IncidentTaskResponse] = []
    # Logs / evidence (read-only investigation steps)
    steps: list[IncidentStepResponse] = []
    # Linked artifacts
    war_room: WarRoomView | None = None
    postmortem: PostmortemView | None = None
    business_impact: BusinessImpactView | None = None

    @field_validator("ai_findings", mode="before")
    @classmethod
    def _none_to_list(cls, v):
        return v or []
