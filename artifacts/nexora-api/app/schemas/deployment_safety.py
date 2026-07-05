"""Sprint 42D — Safe Deployment Intelligence schemas (advisory, read-only)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.deployment_risk import DeploymentRiskInsights


class DeploymentSafetyAnalyzeRequest(BaseModel):
    """Advisory pre-deployment safety request. All fields describe a *candidate*
    deployment; nothing here executes or blocks anything."""

    service: str | None = Field(default=None, max_length=200)
    environment: str | None = Field(default="production", max_length=50)
    version: str | None = Field(default=None, max_length=120)
    provider: str | None = Field(default=None, max_length=40)
    project_id: str | None = Field(default=None, max_length=36)
    # Optional change-set signals forwarded to the 41D risk analyzer.
    commit_count: int = Field(default=0, ge=0)
    changed_files: int = Field(default=0, ge=0)
    has_database_migration: bool = False
    has_infrastructure_changes: bool = False
    has_config_changes: bool = False
    production_only: bool = False


class ReadinessCheck(BaseModel):
    name: str
    status: str  # PASS / WARN / FAIL
    detail: str


class BlastRadius(BaseModel):
    level: str  # LOW / MEDIUM / HIGH / CRITICAL
    affected_services: list[str] = []
    dependent_services: list[str] = []
    customer_impact: list[str] = []


class DeploymentSafetyReport(BaseModel):
    analysis_id: str | None = None
    service: str | None = None
    environment: str | None = None
    version: str | None = None
    provider: str | None = None

    safety_score: int
    confidence: float
    readiness: str  # READY / AT_RISK / NOT_READY
    recommendation: str

    risk_score: int
    risk_level: str

    blast_radius: BlastRadius
    recommended_strategy: str
    strategy_rationale: str
    recommended_window: str
    avoid_windows: list[str] = []

    readiness_checks: list[ReadinessCheck] = []
    warnings: list[str] = []
    history: DeploymentRiskInsights
    created_at: datetime | None = None


class DeploymentSafetyAnalysisSummary(BaseModel):
    id: str
    service: str | None = None
    environment: str | None = None
    version: str | None = None
    safety_score: int
    readiness: str
    blast_radius: str
    recommended_strategy: str
    risk_score: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DeploymentSafetyDashboard(BaseModel):
    total_analyses: int = 0
    ready_count: int = 0
    at_risk_count: int = 0
    not_ready_count: int = 0
    average_safety_score: int | None = None
    recent_analyses: list[DeploymentSafetyAnalysisSummary] = []
