"""Pydantic schemas for product excellence APIs (Sprint 63A)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class InboxNotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    body: str
    category: str
    priority: str
    read_at: datetime | None = None
    pinned: bool = False
    snoozed_until: datetime | None = None
    action_url: str | None = None
    group_key: str | None = None
    created_at: datetime


class SavedViewRequest(BaseModel):
    name: str
    view_type: str = "filter"
    definition: dict[str, Any] | None = None
    is_shared: bool = False
    is_default: bool = False


class SavedViewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    view_type: str
    definition: dict[str, Any] | None = None
    is_shared: bool
    is_default: bool
    user_id: str
    created_at: datetime


class DashboardRequest(BaseModel):
    name: str
    widgets: list[dict[str, Any]] | None = None
    is_shared: bool = False
    is_default: bool = False


class DashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    widgets: list[dict[str, Any]] | None = None
    is_shared: bool
    is_default: bool
    user_id: str
    created_at: datetime


class ReportScheduleRequest(BaseModel):
    name: str
    report_type: str = "executive"
    cadence: str = "monthly"
    export_format: str = "pdf"
    delivery_channel: str = "email"
    delivery_target: str


class ReportScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    report_type: str
    cadence: str
    export_format: str
    delivery_channel: str
    delivery_target: str
    enabled: bool
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    created_at: datetime


class CommentRequest(BaseModel):
    body: str
    parent_id: str | None = None
    attachments: list[dict[str, Any]] | None = None


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    resource_type: str
    resource_id: str
    parent_id: str | None = None
    author_id: str
    body: str
    mentions: list[str] | None = None
    attachments: list[dict[str, Any]] | None = None
    created_at: datetime


class ReactionRequest(BaseModel):
    emoji: str
    comment_id: str | None = None


class PreferenceRequest(BaseModel):
    key: str
    value: Any


class AnalyticsTrackRequest(BaseModel):
    event_name: str
    properties: dict[str, Any] | None = None
    session_id: str | None = None


class CommandPaletteResponse(BaseModel):
    query: str
    results: list[dict[str, Any]]


class TimelineResponse(BaseModel):
    resource_type: str
    resource_id: str
    items: list[dict[str, Any]]
