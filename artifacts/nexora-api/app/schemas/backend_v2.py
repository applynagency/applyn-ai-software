from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.backend_v2 import BackendV2RunStatus


class BackendV2RunRequest(BaseModel):
    requirement_id: str
    backend_v1_run_id: str | None = None


class FileSpecItem(BaseModel):
    id: str
    path: str
    name: str
    description: str
    purpose: str | None = None
    exports: list[str] = []
    dependencies: list[str] = []


class BackendDeveloperV2Output(BaseModel):
    file_structure: dict[str, Any] = Field(default_factory=dict)
    router_files: list[FileSpecItem] = []
    schema_files: list[FileSpecItem] = []
    model_files: list[FileSpecItem] = []
    repository_files: list[FileSpecItem] = []
    service_files: list[FileSpecItem] = []
    dependency_files: list[FileSpecItem] = []
    middleware_files: list[FileSpecItem] = []
    background_job_files: list[FileSpecItem] = []
    integration_files: list[FileSpecItem] = []
    configuration_files: list[FileSpecItem] = []
    migration_files: list[FileSpecItem] = []
    test_files: list[FileSpecItem] = []
    infrastructure_files: list[FileSpecItem] = []


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class BackendV2ArtifactResponse(BaseModel):
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


class BackendV2RunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    backend_v1_run_id: str | None
    status: BackendV2RunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: BackendV2ArtifactResponse | None = None

    model_config = {"from_attributes": True}


class BackendV2RunListResponse(BaseModel):
    items: list[BackendV2RunResponse]
    total: int
