"""Sprint 44A — Postmortem schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PostmortemActionItem(BaseModel):
    title: str
    detail: str | None = None
    owner: str | None = None
    status: str | None = None
    source: str | None = None
    risk_level: str | None = None


class GeneratePostmortemRequest(BaseModel):
    # Regenerate even if a postmortem already exists for the incident.
    force: bool = True


class PostmortemUpdateRequest(BaseModel):
    """Sprint 58A.4 — human edits to an auto-generated postmortem."""

    title: str | None = Field(default=None, max_length=255)
    executive_summary: str | None = None
    impact_analysis: str | None = None
    timeline_summary: str | None = None
    root_cause: str | None = None
    triggering_change: str | None = None
    resolution: str | None = None
    lessons_learned: str | None = None
    action_items: list[PostmortemActionItem] | None = None
    content_markdown: str | None = None


class PostmortemResponse(BaseModel):
    id: str
    organization_id: str
    investigation_id: str
    title: str
    status: str
    severity: str | None = None
    source: str | None = None
    confidence_score: int | None = None
    version: int
    generated_by: str

    executive_summary: str | None = None
    impact_analysis: str | None = None
    timeline_summary: str | None = None
    root_cause: str | None = None
    triggering_change: str | None = None
    resolution: str | None = None
    lessons_learned: str | None = None

    action_items: list[PostmortemActionItem] = Field(default_factory=list)
    content_markdown: str | None = None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PostmortemSummary(BaseModel):
    id: str
    organization_id: str
    investigation_id: str
    title: str
    status: str
    severity: str | None = None
    confidence_score: int | None = None
    version: int
    generated_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PostmortemListResponse(BaseModel):
    items: list[PostmortemSummary] = []
    total: int = 0
    offset: int = 0
    limit: int = 50
