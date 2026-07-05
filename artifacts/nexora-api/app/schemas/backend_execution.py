from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.backend_execution import BackendExecutionRunStatus


class BackendExecutionRunRequest(BaseModel):
    requirement_id: str
    backend_v3_run_id: str | None = None
    backend_code_review_run_id: str | None = None


class BackendExecutionOutput(BaseModel):
    build_status: str
    validation_status: str
    ruff_results: dict[str, Any] = Field(default_factory=dict)
    mypy_results: dict[str, Any] = Field(default_factory=dict)
    pytest_results: dict[str, Any] = Field(default_factory=dict)
    migration_results: dict[str, Any] = Field(default_factory=dict)
    startup_results: dict[str, Any] = Field(default_factory=dict)
    dependency_results: dict[str, Any] = Field(default_factory=dict)
    environment_results: dict[str, Any] = Field(default_factory=dict)
    execution_logs: list[str] = []
    approval_status: str


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, Any] = {}


class BackendExecutionArtifactResponse(BaseModel):
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


class BackendExecutionRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    backend_v3_run_id: str | None
    backend_code_review_run_id: str | None
    status: BackendExecutionRunStatus
    build_status: str | None
    validation_status: str | None
    approval_status: str | None
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    executor_version: str | None
    artifact: BackendExecutionArtifactResponse | None = None

    model_config = {"from_attributes": True}


class BackendExecutionRunListResponse(BaseModel):
    items: list[BackendExecutionRunResponse]
    total: int
