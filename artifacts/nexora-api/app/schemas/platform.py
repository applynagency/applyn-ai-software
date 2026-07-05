"""Pydantic schemas for the platform convergence APIs (Sprint 62A)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# --- events -----------------------------------------------------------------
class EventPublishRequest(BaseModel):
    event_type: str
    payload: dict[str, Any] | None = None
    aggregate_type: str | None = None
    aggregate_id: str | None = None
    source: str = "api"


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    organization_id: str | None = None
    aggregate_type: str | None = None
    aggregate_id: str | None = None
    payload: dict[str, Any] | None = None
    status: str
    attempts: int
    error: str | None = None
    created_at: datetime


# --- notifications ----------------------------------------------------------
class NotificationSendRequest(BaseModel):
    channel: str
    recipient: str
    template_key: str | None = None
    locale: str = "en"
    subject: str | None = None
    body: str | None = None
    context: dict[str, Any] | None = None


class NotificationTemplateRequest(BaseModel):
    key: str
    channel: str
    body_template: str
    subject_template: str | None = None
    locale: str = "en"
    scope_global: bool = False


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    channel: str
    recipient: str
    template_key: str | None = None
    status: str
    provider: str | None = None
    attempts: int
    error: str | None = None
    created_at: datetime


# --- search -----------------------------------------------------------------
class SearchResultItem(BaseModel):
    type: str
    id: str
    title: str
    snippet: str = ""
    url: str | None = None
    score: float = 0.0
    organization_id: str | None = None


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResultItem]


# --- activity ---------------------------------------------------------------
class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    organization_id: str | None = None
    actor_id: str | None = None
    verb: str
    object_type: str | None = None
    object_id: str | None = None
    summary: str
    created_at: datetime


# --- config -----------------------------------------------------------------
class ConfigSetRequest(BaseModel):
    key: str
    value: Any = None
    scope: str = "organization"
    is_feature_flag: bool = False
    is_secret_ref: bool = False


class ConfigValueResponse(BaseModel):
    key: str
    value: Any = None


class ConfigMapResponse(BaseModel):
    values: dict[str, Any]


# --- plugins ----------------------------------------------------------------
class PluginCatalogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    version: str
    description: str | None = None
    author: str | None = None
    capabilities: dict[str, Any] | None = None


class PluginInstallRequest(BaseModel):
    slug: str
    config: dict[str, Any] | None = None


class OrganizationPluginResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    plugin_slug: str
    status: str
    version: str
    created_at: datetime


# --- execution --------------------------------------------------------------
class ExecutionSubmitRequest(BaseModel):
    task_name: str
    job_type: str
    params: dict[str, Any] | None = None
    priority: str = "default"
    delay_seconds: float | None = None


class CheckpointRequest(BaseModel):
    label: str | None = None
    state: dict[str, Any] | None = None


class ApprovalRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)
