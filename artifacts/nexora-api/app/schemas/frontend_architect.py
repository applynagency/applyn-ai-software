from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.frontend_architect import FrontendArchitectRunStatus


class FrontendArchitectRunRequest(BaseModel):
    requirement_id: str
    uiux_run_id: str | None = None


class RouteDefinition(BaseModel):
    id: str
    path: str
    name: str
    page_id: str | None = None
    layout: str | None = None
    auth_required: bool = True


class PageDefinition(BaseModel):
    id: str
    name: str
    route: str
    purpose: str
    layout_id: str | None = None


class LayoutDefinition(BaseModel):
    id: str
    name: str
    description: str
    regions: list[str] = []


class ComponentDefinition(BaseModel):
    id: str
    name: str
    category: str
    description: str
    props: list[str] = []


class FormDefinition(BaseModel):
    id: str
    name: str
    page_id: str
    fields: list[str] = []
    validation_strategy: str | None = None


class FrontendArchitectOutput(BaseModel):
    frontend_stack: dict[str, Any] = Field(default_factory=dict)
    routing_architecture: list[RouteDefinition] = []
    page_architecture: list[PageDefinition] = []
    layout_architecture: list[LayoutDefinition] = []
    component_architecture: list[ComponentDefinition] = []
    state_management: dict[str, Any] = Field(default_factory=dict)
    api_integration: dict[str, Any] = Field(default_factory=dict)
    authentication: dict[str, Any] = Field(default_factory=dict)
    forms: list[FormDefinition] = []
    design_system_mapping: dict[str, Any] = Field(default_factory=dict)
    folder_structure: dict[str, Any] = Field(default_factory=dict)
    deployment_architecture: dict[str, Any] = Field(default_factory=dict)
    development_guidelines: list[str] = []


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class FrontendArchitectArtifactResponse(BaseModel):
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


class FrontendArchitectRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    uiux_run_id: str | None
    status: FrontendArchitectRunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: FrontendArchitectArtifactResponse | None = None

    model_config = {"from_attributes": True}


class FrontendArchitectRunListResponse(BaseModel):
    items: list[FrontendArchitectRunResponse]
    total: int
