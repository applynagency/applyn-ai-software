from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.backend_v1 import BackendV1RunStatus


class BackendV1RunRequest(BaseModel):
    requirement_id: str
    backend_architect_run_id: str | None = None


class ServiceSpecification(BaseModel):
    id: str
    name: str
    description: str
    responsibilities: list[str] = []
    dependencies: list[str] = []


class RepositorySpecification(BaseModel):
    id: str
    name: str
    description: str
    entity: str | None = None
    methods: list[str] = []


class ApiSpecification(BaseModel):
    id: str
    method: str
    path: str
    description: str
    service: str | None = None
    auth_required: bool = True


class DatabaseModelSpecification(BaseModel):
    id: str
    name: str
    description: str
    table_name: str | None = None
    fields: list[str] = []
    relationships: list[str] = []


class ValidationSpecification(BaseModel):
    id: str
    name: str
    description: str
    scope: str | None = None


class BackgroundJobSpecification(BaseModel):
    id: str
    name: str
    description: str
    schedule: str | None = None
    queue: str | None = None


class IntegrationSpecification(BaseModel):
    id: str
    name: str
    type: str
    description: str


class UserRoleSpecification(BaseModel):
    id: str
    name: str
    description: str
    permissions: list[str] = []


class ModuleBreakdownItem(BaseModel):
    id: str
    name: str
    description: str
    services: list[str] = []
    repositories: list[str] = []


class AuthenticationSpecifications(BaseModel):
    strategy: str | None = None
    token_type: str | None = None
    providers: list[str] = []
    middleware: list[str] = []


class AuthorizationSpecifications(BaseModel):
    model: str | None = None
    roles: list[UserRoleSpecification] = []
    policies: list[str] = []


class BackendDeveloperV1Output(BaseModel):
    service_specifications: list[ServiceSpecification] = []
    repository_specifications: list[RepositorySpecification] = []
    api_specifications: list[ApiSpecification] = []
    database_model_specifications: list[DatabaseModelSpecification] = []
    authentication_specifications: AuthenticationSpecifications = Field(
        default_factory=AuthenticationSpecifications
    )
    authorization_specifications: AuthorizationSpecifications = Field(
        default_factory=AuthorizationSpecifications
    )
    validation_specifications: list[ValidationSpecification] = []
    background_job_specifications: list[BackgroundJobSpecification] = []
    integration_specifications: list[IntegrationSpecification] = []
    folder_structure: dict[str, Any] = Field(default_factory=dict)
    module_breakdown: list[ModuleBreakdownItem] = []
    implementation_guidelines: list[str] = []


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class BackendV1ArtifactResponse(BaseModel):
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


class BackendV1RunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    backend_architect_run_id: str | None
    status: BackendV1RunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: BackendV1ArtifactResponse | None = None

    model_config = {"from_attributes": True}


class BackendV1RunListResponse(BaseModel):
    items: list[BackendV1RunResponse]
    total: int
