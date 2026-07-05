from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.backend_architect import BackendArchitectRunStatus


class BackendArchitectRunRequest(BaseModel):
    requirement_id: str
    business_analyst_run_id: str | None = None


class ServiceDefinition(BaseModel):
    id: str
    name: str
    description: str
    responsibilities: list[str] = []


class ApiDefinition(BaseModel):
    id: str
    method: str
    path: str
    description: str
    service: str | None = None
    auth_required: bool = True


class DatabaseEntity(BaseModel):
    id: str
    name: str
    description: str
    tables: list[str] = []
    relationships: list[str] = []


class IntegrationDefinition(BaseModel):
    id: str
    name: str
    type: str
    description: str


class SecurityControl(BaseModel):
    id: str
    name: str
    description: str
    category: str | None = None


class UserRole(BaseModel):
    id: str
    name: str
    description: str
    permissions: list[str] = []


class AuthenticationArchitecture(BaseModel):
    strategy: str | None = None
    token_type: str | None = None
    providers: list[str] = []
    session_management: str | None = None


class AuthorizationArchitecture(BaseModel):
    model: str | None = None
    roles: list[UserRole] = []
    policies: list[str] = []


class SecurityArchitecture(BaseModel):
    controls: list[SecurityControl] = []
    compliance: list[str] = []
    threat_mitigations: list[str] = []


class BackendArchitectOutput(BaseModel):
    backend_stack: dict[str, Any] = Field(default_factory=dict)
    service_architecture: list[ServiceDefinition] = []
    api_architecture: list[ApiDefinition] = []
    database_architecture: list[DatabaseEntity] = []
    authentication_architecture: AuthenticationArchitecture = Field(
        default_factory=AuthenticationArchitecture
    )
    authorization_architecture: AuthorizationArchitecture = Field(
        default_factory=AuthorizationArchitecture
    )
    integration_architecture: list[IntegrationDefinition] = []
    caching_architecture: dict[str, Any] = Field(default_factory=dict)
    event_architecture: dict[str, Any] = Field(default_factory=dict)
    deployment_architecture: dict[str, Any] = Field(default_factory=dict)
    folder_structure: dict[str, Any] = Field(default_factory=dict)
    security_architecture: SecurityArchitecture = Field(default_factory=SecurityArchitecture)
    development_guidelines: list[str] = []


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class BackendArchitectArtifactResponse(BaseModel):
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


class BackendArchitectRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    business_analyst_run_id: str | None
    status: BackendArchitectRunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: BackendArchitectArtifactResponse | None = None

    model_config = {"from_attributes": True}


class BackendArchitectRunListResponse(BaseModel):
    items: list[BackendArchitectRunResponse]
    total: int
