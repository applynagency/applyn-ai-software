"""Sprint 46D - AI Incident War Room schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WarRoomCreate(BaseModel):
    incident_id: str | None = None
    title: str | None = None


class MessageView(BaseModel):
    agent: str
    message_type: str
    content: str
    confidence: int | None = None
    citations: list[str] = []
    sequence: int

    model_config = {"from_attributes": True}


class RemediationStep(BaseModel):
    order: int
    owner_agent: str
    priority: str
    action: str
    rationale: str
    risk_level: str = "MEDIUM"
    requires_approval: bool = True


class WarRoomResponse(BaseModel):
    id: str
    organization_id: str
    incident_id: str | None = None
    title: str
    status: str
    summary: str | None = None
    consensus_rca: str | None = None
    remediation_plan: list[RemediationStep] = []
    confidence_score: int = 0
    participating_agents: list[str] = []
    requires_approval: bool = True
    autonomous_execution: bool = False
    message_count: int = 0
    messages: list[MessageView] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class WarRoomSummary(BaseModel):
    id: str
    incident_id: str | None = None
    title: str
    status: str
    confidence_score: int = 0
    message_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}
