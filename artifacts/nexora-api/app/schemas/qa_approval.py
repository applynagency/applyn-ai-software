from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.qa_approval import QAApprovalRunStatus, QAStatus


class QAApprovalRunRequest(BaseModel):
    requirement_id: str
    integration_test_run_id: str | None = None
    security_test_run_id: str | None = None
    performance_test_run_id: str | None = None


class QAApprovalOutput(BaseModel):
    qa_status: QAStatus
    quality_score: int = Field(ge=0, le=100)
    findings: list[str] = []
    warnings: list[str] = []
    recommendation: str = ""


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class QAApprovalArtifactResponse(BaseModel):
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


class QAApprovalRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    integration_test_run_id: str | None
    security_test_run_id: str | None
    performance_test_run_id: str | None
    status: QAApprovalRunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: QAApprovalArtifactResponse | None = None

    model_config = {"from_attributes": True}


class QAApprovalRunListResponse(BaseModel):
    items: list[QAApprovalRunResponse]
    total: int
