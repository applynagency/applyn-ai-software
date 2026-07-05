from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.backend_v3 import BackendV3RunStatus


class BackendV3RunRequest(BaseModel):
    requirement_id: str
    backend_v2_run_id: str | None = None


class GeneratedFile(BaseModel):
    path: str
    content: str


class BackendDeveloperV3Output(BaseModel):
    generated_files: list[GeneratedFile] = []
    project_structure: dict[str, Any] = Field(default_factory=dict)
    requirements_txt: str = ""
    environment_variables: list[dict[str, Any]] = []
    docker_configuration: dict[str, Any] = Field(default_factory=dict)
    readme: str = ""


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int | bool] = {}


class BackendV3ArtifactResponse(BaseModel):
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


class BackendV3RunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    backend_v2_run_id: str | None
    status: BackendV3RunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: BackendV3ArtifactResponse | None = None

    model_config = {"from_attributes": True}


class BackendV3RunListResponse(BaseModel):
    items: list[BackendV3RunResponse]
    total: int
