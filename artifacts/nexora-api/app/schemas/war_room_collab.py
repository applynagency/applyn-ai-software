"""Schemas for the collaborative war room (real-time incident response)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------- messages
class LiveMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    message_type: str = "INFO"
    parent_message_id: str | None = None
    # Mention targets: human user ids and/or AI agent names (e.g. "SRE", "COPILOT").
    mentions: list[str] = []


class MentionView(BaseModel):
    type: str  # "user" | "agent"
    id: str
    label: str


class LiveMessageView(BaseModel):
    id: str
    war_room_id: str
    author_type: str
    agent: str
    user_id: str | None = None
    user_name: str | None = None
    message_type: str
    content: str
    confidence: int | None = None
    citations: list[str] = []
    mentions: list[MentionView] = []
    parent_message_id: str | None = None
    sequence: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("citations", "mentions", mode="before")
    @classmethod
    def _none_to_empty(cls, v):
        # Legacy / AI / system rows may persist NULL for these JSON columns.
        return v or []


# --------------------------------------------------------------- participants
class ParticipantView(BaseModel):
    user_id: str
    user_name: str | None = None
    role: str | None = None
    is_active: bool = True
    online: bool = False
    last_seen_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PresenceUser(BaseModel):
    user_id: str
    name: str
    connections: int


class PresenceView(BaseModel):
    war_room_id: str
    online: list[PresenceUser] = []
    participants: list[ParticipantView] = []


# --------------------------------------------------------------- attachments
class AttachmentView(BaseModel):
    id: str
    war_room_id: str
    message_id: str | None = None
    filename: str
    content_type: str
    size_bytes: int
    kind: str
    uploaded_by: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --------------------------------------------------------------- evidence
class EvidenceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    attachment_id: str | None = None


class EvidenceView(BaseModel):
    id: str
    war_room_id: str
    title: str
    description: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    attachment_id: str | None = None
    added_by: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --------------------------------------------------------------- approvals
class ApprovalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    kind: str = "REMEDIATION"
    payload: dict | None = None


class ApprovalDecision(BaseModel):
    decision: str  # "APPROVE" | "REJECT"
    reason: str | None = None


class ApprovalView(BaseModel):
    id: str
    war_room_id: str
    title: str
    description: str | None = None
    kind: str
    payload: dict | None = None
    status: str
    requested_by: str | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
    reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --------------------------------------------------------------- AI participant
class AIPromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    parent_message_id: str | None = None
