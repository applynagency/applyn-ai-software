from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.approval import ApprovalRunStatus


class ApprovalRunRequest(BaseModel):
    requirement_id: str
    fullstack_assembly_run_id: str | None = None


class ApprovalWorkflowOutput(BaseModel):
    approval_summary: dict[str, Any] = Field(default_factory=dict)
    review_checklist: list[dict[str, Any]] = []
    deployment_readiness: dict[str, Any] = Field(default_factory=dict)
    recommendation: str
    approval_status: str


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, Any] = {}


class ApprovalDecisionRequest(BaseModel):
    reviewer_notes: str | None = None


class ApprovalArtifactResponse(BaseModel):
    id: str
    run_id: str
    artifact_json: dict[str, Any]
    artifact_markdown: str
    approval_status: str | None
    recommendation: str | None
    validation_score: float | None
    processor_version: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    fullstack_assembly_run_id: str | None
    frontend_execution_run_id: str | None
    status: ApprovalRunStatus
    approval_status: str | None
    recommendation: str | None
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    validation_score: float | None
    processor_version: str | None
    reviewer_notes: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    approval_history: list[dict[str, Any]] = []
    artifact: ApprovalArtifactResponse | None = None

    model_config = {"from_attributes": True}


class ApprovalRunListResponse(BaseModel):
    items: list[ApprovalRunResponse]
    total: int
