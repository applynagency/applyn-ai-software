from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.integration_test import IntegrationTestRunStatus


class IntegrationTestRunRequest(BaseModel):
    requirement_id: str
    frontend_execution_run_id: str | None = None
    backend_execution_run_id: str | None = None
    unit_test_run_id: str | None = None


class IntegrationTestItem(BaseModel):
    id: str
    name: str
    description: str
    expected_result: str | None = None


class IntegrationTestOutput(BaseModel):
    api_test_cases: list[IntegrationTestItem] = []
    frontend_backend_flows: list[IntegrationTestItem] = []
    database_validation: list[IntegrationTestItem] = []
    integration_coverage: dict[str, Any] = {}


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class IntegrationTestArtifactResponse(BaseModel):
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


class IntegrationTestRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    frontend_execution_run_id: str | None
    backend_execution_run_id: str | None
    unit_test_run_id: str | None
    status: IntegrationTestRunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: IntegrationTestArtifactResponse | None = None

    model_config = {"from_attributes": True}


class IntegrationTestRunListResponse(BaseModel):
    items: list[IntegrationTestRunResponse]
    total: int
