from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.lifecycle import (
    ApplicationVersionStatus,
    RegenerationRunStatus,
    RegenerationScope,
)


class ChangeRequestCreate(BaseModel):
    requirement_id: str
    title: str
    description: str
    scope: RegenerationScope = RegenerationScope.FULL_STACK


class ChangeRequestDecision(BaseModel):
    approved: bool
    comment: str | None = None


class ImpactAnalysisRequest(BaseModel):
    regeneration_run_id: str


class RegenerationExecuteRequest(BaseModel):
    regeneration_run_id: str


class ApplicationVersionResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    version: str
    status: ApplicationVersionStatus
    release_date: datetime | None
    change_summary: str | None
    deployment_url: str | None
    approval_history: dict[str, Any]
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RegenerationArtifactResponse(BaseModel):
    id: str
    run_id: str
    artifact_type: str
    artifact_json: dict[str, Any]
    artifact_markdown: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ReleaseCreate(BaseModel):
    requirement_id: str
    title: str
    description: str
    scope: RegenerationScope = RegenerationScope.FULL_STACK
    regeneration_run_id: str | None = None


class RegenerationRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    from_version_id: str | None
    target_version: str
    scope: RegenerationScope
    change_request_title: str
    change_request_description: str
    impact_analysis: dict[str, Any]
    execution_plan: dict[str, Any]
    status: RegenerationRunStatus
    risk_score: float | None
    estimated_effort_hours: float | None
    executed_agents: list[str]
    warnings: list[str]
    created_by: str
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime
    artifact: RegenerationArtifactResponse | None = None
    customer_message: str | None = None
    approval_status: str | None = None
    approval_comment: str | None = None

    model_config = {"from_attributes": True}


class RegenerationRunListResponse(BaseModel):
    items: list[RegenerationRunResponse]
    total: int


class ReleaseHistoryResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    application_version_id: str
    regeneration_run_id: str | None
    fullstack_assembly_run_id: str | None
    approval_run_id: str | None
    deployment_run_id: str | None
    release_date: datetime | None
    change_summary: str | None
    deployment_url: str | None
    approval_history: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    customer_message: str | None = None

    model_config = {"from_attributes": True}


class ReleaseHistoryListResponse(BaseModel):
    items: list[ReleaseHistoryResponse]
    total: int
