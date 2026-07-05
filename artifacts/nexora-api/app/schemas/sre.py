"""Pydantic schemas for autonomous SRE APIs (Sprint 63B)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CommanderStartRequest(BaseModel):
    incident_id: str


class CommanderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_id: str
    agent_run_id: str | None = None
    status: str
    investigation_plan: list[dict[str, Any]] | None = None
    findings_summary: str | None = None
    remediation_summary: str | None = None
    created_at: datetime


class RCAHypothesisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_id: str
    hypothesis: str
    confidence: float
    evidence: list[dict[str, Any]] | None = None
    sources: list[dict[str, Any]] | None = None
    status: str
    created_at: datetime


class RunbookExecuteRequest(BaseModel):
    variables: dict[str, Any] | None = None


class RunbookExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    runbook_id: str
    job_id: str | None = None
    status: str
    variables: dict[str, Any] | None = None
    current_step: int
    checkpoints: list[dict[str, Any]] | None = None
    created_at: datetime


class RemediationWorkflowRequest(BaseModel):
    incident_id: str
    actions: list[dict[str, Any]]


class ChangeRiskRequest(BaseModel):
    service: str | None = None
    environment: str | None = None
    provider: str | None = None
    commit_count: int = 0
    changed_files: int = 0
    has_database_migration: bool = False
    has_infrastructure_changes: bool = False
    production_only: bool = False


class PredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    prediction_type: str
    target: str
    score: float
    risk_level: str
    horizon_hours: int
    explanation: str | None = None
    evidence: list[dict[str, Any]] | None = None
    created_at: datetime


class AIRecommendationResponse(BaseModel):
    id: str
    title: str
    confidence: float
    evidence: list[dict[str, Any]] = []
    affected_resources: list[dict[str, Any]] = []
    reasoning_summary: str | None = None
    retrieved_sources: list[dict[str, Any]] = []
    generated_actions: list[dict[str, Any]] = []


class OperationsCenterResponse(BaseModel):
    organization_id: str
    active_incidents: list[dict[str, Any]]
    ai_investigations: list[dict[str, Any]]
    deployments: dict[str, Any]
    health: dict[str, Any]
    predictions: list[dict[str, Any]]
    notifications_unread: int
    ai_recommendations: list[AIRecommendationResponse]
    updated_at: str


class ExecutiveAIReportRequest(BaseModel):
    cadence: str = Field(default="WEEKLY", pattern="^(DAILY|WEEKLY|MONTHLY)$")


class LearnFromIncidentRequest(BaseModel):
    incident_id: str
