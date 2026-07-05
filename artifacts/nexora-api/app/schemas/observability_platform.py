"""Pydantic schemas for Enterprise Observability Platform API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IntegrationCreate(BaseModel):
    name: str
    kind: str
    signal: str
    config: dict = Field(default_factory=dict)
    credential_id: str | None = None
    retention_days: int = 30


class IntegrationView(BaseModel):
    id: str
    name: str
    kind: str
    signal: str
    config: dict
    is_active: bool
    retention_days: int

    model_config = {"from_attributes": True}


class MetricQuery(BaseModel):
    query: str
    window: str = "1h"
    integration_id: str | None = None


class LogQuery(BaseModel):
    query: str
    limit: int = 100
    integration_id: str | None = None


class TraceQuery(BaseModel):
    query: str
    limit: int = 50
    integration_id: str | None = None


class SavedSearchCreate(BaseModel):
    name: str
    signal: str
    query: str
    filters: dict = Field(default_factory=dict)


class SavedSearchView(BaseModel):
    id: str
    name: str
    signal: str
    query: str
    filters: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class CorrelationRequest(BaseModel):
    title: str | None = None
    service_name: str | None = None
    incident_id: str | None = None


class CorrelationView(BaseModel):
    id: str
    title: str
    timeline: dict
    root_cause: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ServiceMapView(BaseModel):
    nodes: list
    edges: list
    metrics_overlay: dict
    critical_path: list


class SLODashboardView(BaseModel):
    services: list
    evaluations: list
    error_budgets: list
    burn_rates: list


class ErrorBudgetView(BaseModel):
    service_id: str | None
    service_name: str | None
    target: float
    remaining_percent: float | None
    burn_rate: float | None
    forecast_days: float | None


class AlertIntelligenceView(BaseModel):
    groups: list
    storms: list
    recommendations: list


class DashboardView(BaseModel):
    golden_signals: dict
    infrastructure: dict
    applications: dict
    alert_summary: dict


class ProvidersView(BaseModel):
    metrics: list[str]
    logs: list[str]
    traces: list[str]
