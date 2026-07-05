from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.fullstack_assembly import FullstackAssemblyRunStatus


class FullstackAssemblyRunRequest(BaseModel):
    requirement_id: str
    frontend_execution_run_id: str | None = None
    backend_execution_run_id: str | None = None


class FullstackAssemblyOutput(BaseModel):
    application_manifest: dict[str, Any] = Field(default_factory=dict)
    frontend_package: dict[str, Any] = Field(default_factory=dict)
    backend_package: dict[str, Any] = Field(default_factory=dict)
    deployment_assets: dict[str, Any] = Field(default_factory=dict)
    environment_variables: list[dict[str, Any]] = []
    docker_assets: dict[str, Any] = Field(default_factory=dict)
    infrastructure_templates: dict[str, Any] = Field(default_factory=dict)
    health_checks: dict[str, Any] = Field(default_factory=dict)
    startup_configuration: dict[str, Any] = Field(default_factory=dict)
    release_metadata: dict[str, Any] = Field(default_factory=dict)
    readme: str = ""
    assembly_status: str
    package_metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, Any] = {}


class FullstackAssemblyArtifactResponse(BaseModel):
    id: str
    run_id: str
    artifact_json: dict[str, Any]
    artifact_markdown: str
    assembly_status: str | None
    validation_score: float | None
    assembler_version: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FullstackAssemblyRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    frontend_execution_run_id: str | None
    backend_execution_run_id: str | None
    status: FullstackAssemblyRunStatus
    assembly_status: str | None
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    validation_score: float | None
    assembler_version: str | None
    artifact: FullstackAssemblyArtifactResponse | None = None

    model_config = {"from_attributes": True}


class FullstackAssemblyRunListResponse(BaseModel):
    items: list[FullstackAssemblyRunResponse]
    total: int
