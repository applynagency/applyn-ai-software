from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.backend_code_review import BackendApprovalStatus, BackendCodeReviewRunStatus

REVIEW_CATEGORIES = [
    "Architecture",
    "FastAPI",
    "SQLAlchemy",
    "Pydantic",
    "Authentication",
    "Authorization",
    "Security",
    "Performance",
    "Testing",
    "API Design",
    "Code Quality",
    "Database Design",
]


class BackendCodeReviewRunRequest(BaseModel):
    requirement_id: str
    backend_v3_run_id: str | None = None


class ReviewIssue(BaseModel):
    id: str
    category: str
    severity: str
    title: str
    description: str
    file_path: str | None = None
    recommendation: str | None = None


class ReviewRecommendation(BaseModel):
    id: str
    category: str
    title: str
    description: str
    priority: str


class BackendCodeReviewOutput(BaseModel):
    review_score: float
    approval_status: BackendApprovalStatus
    issues: list[ReviewIssue] = []
    recommendations: list[ReviewRecommendation] = []
    category_scores: dict[str, float] = Field(default_factory=dict)
    summary: str = ""


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, Any] = {}


class BackendCodeReviewArtifactResponse(BaseModel):
    id: str
    run_id: str
    artifact_json: dict[str, Any]
    artifact_markdown: str
    review_score: float | None
    approval_status: str | None
    prompt_version: str | None
    model_used: str | None
    tokens_used: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BackendCodeReviewRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    backend_v3_run_id: str | None
    status: BackendCodeReviewRunStatus
    approval_status: str | None
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    review_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: BackendCodeReviewArtifactResponse | None = None

    model_config = {"from_attributes": True}


class BackendCodeReviewRunListResponse(BaseModel):
    items: list[BackendCodeReviewRunResponse]
    total: int
