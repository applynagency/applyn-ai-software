from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.frontend_v1 import FrontendV1RunStatus


class FrontendV1RunRequest(BaseModel):
    requirement_id: str
    frontend_architect_run_id: str | None = None


class RouteStructureItem(BaseModel):
    id: str
    path: str
    name: str
    page_id: str | None = None
    layout_id: str | None = None


class LayoutStructureItem(BaseModel):
    id: str
    name: str
    description: str
    file_path: str | None = None


class PageStructureItem(BaseModel):
    id: str
    name: str
    route: str
    file_path: str
    purpose: str


class ComponentStructureItem(BaseModel):
    id: str
    name: str
    category: str
    file_path: str
    description: str


class FormArchitectureItem(BaseModel):
    id: str
    name: str
    page_id: str
    fields: list[str] = []
    validation_approach: str | None = None


class ModuleBreakdownItem(BaseModel):
    id: str
    name: str
    description: str
    pages: list[str] = []
    components: list[str] = []


class FrontendDeveloperV1Output(BaseModel):
    project_structure: dict[str, Any] = Field(default_factory=dict)
    route_structure: list[RouteStructureItem] = []
    layout_structure: list[LayoutStructureItem] = []
    page_structure: list[PageStructureItem] = []
    component_structure: list[ComponentStructureItem] = []
    api_client_structure: dict[str, Any] = Field(default_factory=dict)
    state_management: dict[str, Any] = Field(default_factory=dict)
    form_architecture: list[FormArchitectureItem] = []
    validation_strategy: dict[str, Any] = Field(default_factory=dict)
    folder_organization: dict[str, Any] = Field(default_factory=dict)
    development_conventions: list[str] = []
    module_breakdown: list[ModuleBreakdownItem] = []


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class FrontendV1ArtifactResponse(BaseModel):
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


class FrontendV1RunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    frontend_architect_run_id: str | None
    status: FrontendV1RunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: FrontendV1ArtifactResponse | None = None

    model_config = {"from_attributes": True}


class FrontendV1RunListResponse(BaseModel):
    items: list[FrontendV1RunResponse]
    total: int
