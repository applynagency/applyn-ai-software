from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.frontend_execution import FrontendExecutionRunStatus


class FrontendExecutionRunRequest(BaseModel):
    requirement_id: str
    frontend_v3_run_id: str | None = None
    frontend_code_review_run_id: str | None = None


class StepResult(BaseModel):
    status: str
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: int | None = None


class FrontendExecutionOutput(BaseModel):
    build_status: str
    validation_status: str
    lint_results: dict[str, Any] = Field(default_factory=dict)
    typecheck_results: dict[str, Any] = Field(default_factory=dict)
    test_results: dict[str, Any] = Field(default_factory=dict)
    build_results: dict[str, Any] = Field(default_factory=dict)
    install_results: dict[str, Any] = Field(default_factory=dict)
    execution_logs: list[str] = []
    approval_status: str


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, Any] = {}


class FrontendExecutionArtifactResponse(BaseModel):
    id: str
    run_id: str
    artifact_json: dict[str, Any]
    artifact_markdown: str
    build_status: str | None
    validation_status: str | None
    approval_status: str | None
    executor_version: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FrontendExecutionRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    frontend_v3_run_id: str | None
    frontend_code_review_run_id: str | None
    status: FrontendExecutionRunStatus
    build_status: str | None
    validation_status: str | None
    approval_status: str | None
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    executor_version: str | None
    artifact: FrontendExecutionArtifactResponse | None = None

    model_config = {"from_attributes": True}


class FrontendExecutionRunListResponse(BaseModel):
    items: list[FrontendExecutionRunResponse]
    total: int
