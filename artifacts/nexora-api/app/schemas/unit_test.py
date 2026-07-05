from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.unit_test import UnitTestRunStatus


class UnitTestRunRequest(BaseModel):
    requirement_id: str
    qa_architect_run_id: str | None = None


class UnitTestSpecification(BaseModel):
    id: str
    name: str
    description: str
    target_module: str
    test_type: str
    assertions: list[str] = []


class TestFixture(BaseModel):
    id: str
    name: str
    description: str
    setup: str | None = None
    teardown: str | None = None


class UnitTestGeneratorOutput(BaseModel):
    frontend_unit_test_specifications: list[UnitTestSpecification] = []
    backend_unit_test_specifications: list[UnitTestSpecification] = []
    mock_strategy: dict[str, Any] = Field(default_factory=dict)
    test_fixtures: list[TestFixture] = []
    coverage_targets: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class UnitTestArtifactResponse(BaseModel):
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


class UnitTestRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    qa_architect_run_id: str | None
    status: UnitTestRunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: UnitTestArtifactResponse | None = None

    model_config = {"from_attributes": True}


class UnitTestRunListResponse(BaseModel):
    items: list[UnitTestRunResponse]
    total: int
