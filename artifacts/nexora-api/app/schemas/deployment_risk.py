"""Schemas for Sprint 41D — Deployment Risk Intelligence (read-only)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DeploymentRiskReason(BaseModel):
    """A single explainable contribution to the risk score."""

    factor: str
    detail: str
    weight: int


class DeploymentRiskInsights(BaseModel):
    """Historical deployment/incident health for the (optionally filtered) scope."""

    total_deployments: int = 0
    successful_deployments: int = 0
    failed_deployments: int = 0
    rolled_back_deployments: int = 0
    success_rate: float | None = None
    rollback_rate: float | None = None
    mttr_minutes: float | None = None
    incident_count: int = 0
    incident_frequency_per_week: float | None = None
    last_successful_deployment: datetime | None = None
    last_failed_deployment: datetime | None = None


class DeploymentRiskTrendPoint(BaseModel):
    period: str
    score: int
    deployments: int = 0
    failures: int = 0


class DeploymentRiskReport(BaseModel):
    risk_score: int
    risk_level: str
    provider: str | None = None
    environment: str | None = None
    application: str | None = None
    reasons: list[DeploymentRiskReason] = []
    insights: DeploymentRiskInsights
    likely_impact: list[str] = []
    recommended_actions: list[str] = []
    trend: list[DeploymentRiskTrendPoint] = []


class DeploymentRiskAnalyzeRequest(BaseModel):
    """Predict risk for a *candidate* deployment before it ships.

    All change-set signals are optional, non-secret booleans/counts describing
    the pending change. Nothing here mutates infrastructure.
    """

    provider: str | None = None
    environment: str | None = None
    project_id: str | None = None
    application: str | None = None
    commit_count: int = Field(default=0, ge=0)
    changed_files: int = Field(default=0, ge=0)
    pull_requests: int = Field(default=0, ge=0)
    has_database_migration: bool = False
    has_infrastructure_changes: bool = False
    has_config_changes: bool = False
    production_only: bool = False
