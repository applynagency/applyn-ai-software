"""Sprint 52C — Demo Organization Generator schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DemoTemplateInfo(BaseModel):
    key: str
    name: str
    industry: str
    summary: str
    service_count: int
    incident_count: int
    highlights: list[str] = []


class DemoTemplateListResponse(BaseModel):
    templates: list[DemoTemplateInfo]


class DemoOrgCreateRequest(BaseModel):
    template: str = Field(..., description="Template key, e.g. 'ecommerce'.")
    name: str | None = Field(default=None, max_length=255)


class DemoOrgSummary(BaseModel):
    id: str
    name: str
    slug: str
    template: str
    industry: str
    counts: dict[str, int]
    credentials: dict[str, Any]
    dashboards: list[dict[str, Any]]
    screenshots: list[dict[str, Any]]
    reports: list[dict[str, Any]]


class DemoOrgListItem(BaseModel):
    id: str
    name: str
    slug: str
    template: str
    industry: str
    created_at: datetime
    counts: dict[str, int]


class DemoOrgListResponse(BaseModel):
    items: list[DemoOrgListItem]
    total: int
