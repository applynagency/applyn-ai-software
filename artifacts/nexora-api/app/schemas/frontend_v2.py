from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.frontend_v2 import FrontendV2RunStatus


class FrontendV2RunRequest(BaseModel):
    requirement_id: str
    frontend_v1_run_id: str | None = None


class FileSpecItem(BaseModel):
    id: str
    path: str
    name: str
    description: str
    purpose: str | None = None
    exports: list[str] = []
    dependencies: list[str] = []


class FrontendDeveloperV2Output(BaseModel):
    file_structure: dict[str, Any] = Field(default_factory=dict)
    page_files: list[FileSpecItem] = []
    component_files: list[FileSpecItem] = []
    layout_files: list[FileSpecItem] = []
    service_files: list[FileSpecItem] = []
    store_files: list[FileSpecItem] = []
    hook_files: list[FileSpecItem] = []
    provider_files: list[FileSpecItem] = []
    type_files: list[FileSpecItem] = []
    middleware_files: list[FileSpecItem] = []
    utility_files: list[FileSpecItem] = []
    form_files: list[FileSpecItem] = []
    validation_files: list[FileSpecItem] = []


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class FrontendV2ArtifactResponse(BaseModel):
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


class FrontendV2RunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    frontend_v1_run_id: str | None
    status: FrontendV2RunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: FrontendV2ArtifactResponse | None = None

    model_config = {"from_attributes": True}


class FrontendV2RunListResponse(BaseModel):
    items: list[FrontendV2RunResponse]
    total: int
