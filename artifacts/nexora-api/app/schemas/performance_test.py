from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.performance_test import PerformanceTestRunStatus


class PerformanceTestRunRequest(BaseModel):
    requirement_id: str
    integration_test_run_id: str | None = None
    security_test_run_id: str | None = None


class PerformanceItem(BaseModel):
    id: str
    name: str
    description: str
    target_metric: str | None = None


class PerformanceTestOutput(BaseModel):
    load_test_plan: list[PerformanceItem] = []
    stress_test_plan: list[PerformanceItem] = []
    performance_bottlenecks: list[PerformanceItem] = []
    scaling_recommendations: list[PerformanceItem] = []
    caching_recommendations: list[PerformanceItem] = []


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class PerformanceTestArtifactResponse(BaseModel):
    id: str
    run_id: str
    artifact_json: dict[str, Any]
    artifact_markdown: str
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    tokens_used: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PerformanceTestRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    integration_test_run_id: str | None
    security_test_run_id: str | None
    status: PerformanceTestRunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: PerformanceTestArtifactResponse | None = None

    model_config = {"from_attributes": True}


class PerformanceTestRunListResponse(BaseModel):
    items: list[PerformanceTestRunResponse]
    total: int
