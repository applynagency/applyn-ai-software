"""Sprint 45A — Intelligent Runbook schemas (read-only generation + manual edit)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RunbookGenerateRequest(BaseModel):
    """Generate a runbook for an incident class.

    Provide ``category`` directly, or an ``investigation_id`` to derive it from a
    known incident. ``service`` optionally scopes the runbook.
    """

    category: str | None = None
    service: str | None = None
    title: str | None = None
    investigation_id: str | None = None


class RunbookUpdateRequest(BaseModel):
    """Manual edit — any provided field overrides the generated content and bumps
    the version. All optional."""

    title: str | None = None
    category: str | None = None
    service: str | None = None
    summary: str | None = None
    investigation_steps: list[str] | None = None
    validation_steps: list[str] | None = None
    rollback_steps: list[str] | None = None
    recovery_checklist: list[str] | None = None


class RunbookResponse(BaseModel):
    id: str
    organization_id: str
    title: str
    category: str
    service: str | None = None
    summary: str | None = None
    investigation_steps: list[str] = Field(default_factory=list)
    validation_steps: list[str] = Field(default_factory=list)
    rollback_steps: list[str] = Field(default_factory=list)
    recovery_checklist: list[str] = Field(default_factory=list)
    content_markdown: str | None = None
    source_incident_ids: list[str] = Field(default_factory=list)
    source_incident_count: int = 0
    version: int = 1
    status: str
    source: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RunbookSummary(BaseModel):
    id: str
    title: str
    category: str
    service: str | None = None
    summary: str | None = None
    source_incident_count: int = 0
    version: int = 1
    status: str
    source: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class RunbookListResponse(BaseModel):
    items: list[RunbookSummary] = []
    total: int = 0
    offset: int = 0
    limit: int = 50
