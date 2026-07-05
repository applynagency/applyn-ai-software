from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.security_test import SecurityTestRunStatus


class SecurityTestRunRequest(BaseModel):
    requirement_id: str
    frontend_execution_run_id: str | None = None
    backend_execution_run_id: str | None = None
    integration_test_run_id: str | None = None


class SecurityAssessmentItem(BaseModel):
    id: str
    name: str
    description: str
    severity: str | None = None
    recommendation: str | None = None


class SecurityTestOutput(BaseModel):
    owasp_assessment: list[SecurityAssessmentItem] = []
    authentication_review: list[SecurityAssessmentItem] = []
    authorization_review: list[SecurityAssessmentItem] = []
    input_validation_review: list[SecurityAssessmentItem] = []
    dependency_security_scan: list[SecurityAssessmentItem] = []
    secrets_exposure_review: list[SecurityAssessmentItem] = []


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class SecurityTestArtifactResponse(BaseModel):
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


class SecurityTestRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    frontend_execution_run_id: str | None
    backend_execution_run_id: str | None
    integration_test_run_id: str | None
    status: SecurityTestRunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: SecurityTestArtifactResponse | None = None

    model_config = {"from_attributes": True}


class SecurityTestRunListResponse(BaseModel):
    items: list[SecurityTestRunResponse]
    total: int
