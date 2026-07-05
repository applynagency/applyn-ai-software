from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.qa_architect import QAArchitectRunStatus


class QAArchitectRunRequest(BaseModel):
    requirement_id: str
    frontend_execution_run_id: str | None = None
    backend_execution_run_id: str | None = None


class TestScenario(BaseModel):
    id: str
    name: str
    description: str
    layer: str
    priority: str = "medium"
    coverage_area: str | None = None


class RiskArea(BaseModel):
    id: str
    name: str
    description: str
    severity: str
    mitigation: str | None = None


class UserJourney(BaseModel):
    id: str
    name: str
    description: str
    steps: list[str] = []
    priority: str = "high"


class RegressionScenario(BaseModel):
    id: str
    name: str
    description: str
    trigger: str | None = None
    expected_result: str | None = None


class AcceptanceCriterion(BaseModel):
    id: str
    name: str
    description: str
    verification_method: str | None = None


class QAArchitectOutput(BaseModel):
    test_strategy: str = ""
    test_coverage_matrix: list[TestScenario] = []
    risk_areas: list[RiskArea] = []
    critical_user_journeys: list[UserJourney] = []
    regression_areas: list[RegressionScenario] = []
    acceptance_test_plan: list[AcceptanceCriterion] = []


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class QAArchitectArtifactResponse(BaseModel):
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


class QAArchitectRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    frontend_execution_run_id: str | None
    backend_execution_run_id: str | None
    status: QAArchitectRunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: QAArchitectArtifactResponse | None = None

    model_config = {"from_attributes": True}


class QAArchitectRunListResponse(BaseModel):
    items: list[QAArchitectRunResponse]
    total: int
