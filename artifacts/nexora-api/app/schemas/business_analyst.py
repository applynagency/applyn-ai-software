from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.business_analyst import BusinessAnalystRunStatus


class BusinessAnalystRunRequest(BaseModel):
    requirement_id: str
    product_owner_run_id: str | None = None


class FunctionalRequirement(BaseModel):
    id: str
    title: str
    description: str
    priority: str = "medium"
    module: str | None = None


class NonFunctionalRequirement(BaseModel):
    id: str
    category: str
    description: str
    metric: str | None = None


class RoleDefinition(BaseModel):
    id: str
    name: str
    description: str


class PermissionDefinition(BaseModel):
    id: str
    role: str
    resource: str
    action: str
    description: str


class ModuleDefinition(BaseModel):
    id: str
    name: str
    description: str
    dependencies: list[str] = []


class BusinessRule(BaseModel):
    id: str
    name: str
    description: str
    module: str | None = None


class EntityDefinition(BaseModel):
    id: str
    name: str
    description: str
    attributes: list[str] = []


class UserFlow(BaseModel):
    id: str
    name: str
    actor: str
    steps: list[str] = []


class ApiRequirement(BaseModel):
    id: str
    method: str
    path: str
    description: str
    module: str | None = None


class AcceptanceCriterion(BaseModel):
    id: str
    requirement_id: str
    description: str
    testable: bool = True


class AssumptionItem(BaseModel):
    id: str
    description: str
    impact: str = "medium"


class RiskItem(BaseModel):
    id: str
    description: str
    impact: str = "medium"
    mitigation: str | None = None


class DependencyItem(BaseModel):
    id: str
    name: str
    description: str
    type: str = "internal"


class BusinessAnalystOutput(BaseModel):
    project_summary: dict[str, Any] = Field(default_factory=dict)
    functional_requirements: list[FunctionalRequirement] = []
    non_functional_requirements: list[NonFunctionalRequirement] = []
    roles: list[RoleDefinition] = []
    permissions: list[PermissionDefinition] = []
    modules: list[ModuleDefinition] = []
    business_rules: list[BusinessRule] = []
    entities: list[EntityDefinition] = []
    user_flows: list[UserFlow] = []
    api_requirements: list[ApiRequirement] = []
    acceptance_criteria: list[AcceptanceCriterion] = []
    assumptions: list[AssumptionItem] = []
    risks: list[RiskItem] = []
    dependencies: list[DependencyItem] = []


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class BusinessAnalystArtifactResponse(BaseModel):
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


class BusinessAnalystRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    product_owner_run_id: str | None
    status: BusinessAnalystRunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: BusinessAnalystArtifactResponse | None = None

    model_config = {"from_attributes": True}


class BusinessAnalystRunListResponse(BaseModel):
    items: list[BusinessAnalystRunResponse]
    total: int
