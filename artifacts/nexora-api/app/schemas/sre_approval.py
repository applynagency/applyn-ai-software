from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.sre_approval import SreApprovalRunStatus, SreStatus


class SreApprovalRunRequest(BaseModel):
    requirement_id: str
    kubernetes_run_id: str | None = None
    observability_run_id: str | None = None


class SreApprovalOutput(BaseModel):
    sre_status: SreStatus
    production_readiness_score: int = Field(ge=0, le=100)
    availability_score: int = Field(ge=0, le=100)
    security_score: int = Field(ge=0, le=100)
    performance_score: int = Field(ge=0, le=100)
    cost_score: int = Field(ge=0, le=100)
    operational_readiness_score: int = Field(ge=0, le=100)
    findings: list[str] = []
    warnings: list[str] = []
    recommendation: str = ""


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class SreApprovalArtifactResponse(BaseModel):
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


class SreApprovalRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    kubernetes_run_id: str | None
    observability_run_id: str | None
    status: SreApprovalRunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: SreApprovalArtifactResponse | None = None

    model_config = {"from_attributes": True}


class SreApprovalRunListResponse(BaseModel):
    items: list[SreApprovalRunResponse]
    total: int
