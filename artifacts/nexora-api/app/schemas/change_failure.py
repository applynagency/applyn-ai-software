"""Sprint 44C — Change Failure Prediction schemas (read-only)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChangeFailureAnalyzeRequest(BaseModel):
    """Predict failure likelihood for a *candidate* change before it ships.

    All change-set signals are optional, non-secret booleans/counts describing
    the pending change. Nothing here mutates infrastructure.
    """

    service: str | None = None
    environment: str | None = None
    provider: str | None = None
    version: str | None = None
    project_id: str | None = None
    # change-set metadata
    commit_count: int = Field(default=0, ge=0)
    changed_files: int = Field(default=0, ge=0)
    pull_requests: int = Field(default=0, ge=0)
    has_database_migration: bool = False
    has_infrastructure_changes: bool = False
    has_config_changes: bool = False
    production_only: bool = False


class ContributingFactor(BaseModel):
    factor: str
    detail: str
    points: int
    category: str = "general"


class ChangeFailurePredictionReport(BaseModel):
    prediction_id: str | None = None
    service: str | None = None
    environment: str | None = None
    provider: str | None = None
    version: str | None = None

    failure_probability: int = 0   # 0–100
    confidence_score: float = 0.0  # 0–1
    risk_level: str = "LOW"

    top_contributing_factors: list[ContributingFactor] = []
    contributing_factors: list[ContributingFactor] = []
    likely_failure_modes: list[str] = []
    expected_blast_radius: str = "LOW"
    expected_customer_impact: str = ""
    customer_impact_detail: list[str] = []
    recommended_mitigation_steps: list[str] = []

    # transparency: the raw signals the score was built from.
    signals: dict = {}
    created_at: datetime | None = None


class ChangeFailurePredictionSummary(BaseModel):
    id: str
    service: str | None = None
    environment: str | None = None
    provider: str | None = None
    version: str | None = None
    failure_probability: int
    confidence_score: float
    risk_level: str
    expected_blast_radius: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChangeFailureDashboard(BaseModel):
    total_predictions: int = 0
    low_count: int = 0
    medium_count: int = 0
    high_count: int = 0
    critical_count: int = 0
    average_failure_probability: int | None = None
    highest_risk: list[ChangeFailurePredictionSummary] = []
    recent_predictions: list[ChangeFailurePredictionSummary] = []
