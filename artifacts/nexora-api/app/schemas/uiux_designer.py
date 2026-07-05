from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.uiux_designer import UIUXRunStatus


class UIUXRunRequest(BaseModel):
    requirement_id: str
    business_analyst_run_id: str | None = None


class NavigationGroup(BaseModel):
    id: str
    name: str
    description: str
    items: list[str] = []


class UIUXUserFlow(BaseModel):
    id: str
    name: str
    actor: str
    steps: list[str] = []
    screens: list[str] = []


class ScreenItem(BaseModel):
    id: str
    name: str
    purpose: str
    primary_actions: list[str] = []
    layout_type: str | None = None


class PageHierarchyItem(BaseModel):
    id: str
    name: str
    parent_id: str | None = None
    level: int = 1


class RoleScreenMapping(BaseModel):
    role: str
    screens: list[str] = []
    description: str | None = None


class ComponentItem(BaseModel):
    id: str
    name: str
    category: str
    description: str
    usage: str | None = None


class UIUXDesignerOutput(BaseModel):
    information_architecture: dict[str, Any] = Field(default_factory=dict)
    navigation_structure: list[NavigationGroup] = []
    user_flows: list[UIUXUserFlow] = []
    screen_inventory: list[ScreenItem] = []
    page_hierarchy: list[PageHierarchyItem] = []
    role_screen_mapping: list[RoleScreenMapping] = []
    design_system: dict[str, Any] = Field(default_factory=dict)
    component_inventory: list[ComponentItem] = []
    frontend_handoff: dict[str, Any] = Field(default_factory=dict)
    responsive_guidelines: list[str] = []
    accessibility_guidelines: list[str] = []


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class UIUXArtifactResponse(BaseModel):
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


class UIUXRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    business_analyst_run_id: str | None
    status: UIUXRunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: UIUXArtifactResponse | None = None

    model_config = {"from_attributes": True}


class UIUXRunListResponse(BaseModel):
    items: list[UIUXRunResponse]
    total: int
