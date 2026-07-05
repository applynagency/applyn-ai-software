from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.frontend_v3 import FrontendV3RunStatus


class FrontendV3RunRequest(BaseModel):
    requirement_id: str
    frontend_v2_run_id: str | None = None


class GeneratedFile(BaseModel):
    path: str
    content: str


class FrontendDeveloperV3Output(BaseModel):
    generated_files: list[GeneratedFile] = []
    project_structure: dict[str, Any] = Field(default_factory=dict)
    package_json: dict[str, Any] = Field(default_factory=dict)
    environment_variables: list[dict[str, Any]] = []
    docker_configuration: dict[str, Any] = Field(default_factory=dict)
    readme: str = ""


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int | bool] = {}


class FrontendV3ArtifactResponse(BaseModel):
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


class FrontendV3RunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    frontend_v2_run_id: str | None
    status: FrontendV3RunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: FrontendV3ArtifactResponse | None = None

    model_config = {"from_attributes": True}


class FrontendV3RunListResponse(BaseModel):
    items: list[FrontendV3RunResponse]
    total: int
