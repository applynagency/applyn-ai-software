from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.infrastructure_architect import InfrastructureArchitectRunStatus


class InfrastructureArchitectRunRequest(BaseModel):
    requirement_id: str
    frontend_execution_run_id: str | None = None
    backend_execution_run_id: str | None = None
    qa_approval_run_id: str | None = None


class Environment(BaseModel):
    id: str
    name: str
    description: str
    purpose: str | None = None
    region: str | None = None


class ScalingRule(BaseModel):
    id: str
    name: str
    description: str
    metric: str | None = None
    threshold: str | None = None


class SecurityControl(BaseModel):
    id: str
    name: str
    description: str
    control_type: str | None = None
    implementation: str | None = None


class BackupRecoveryPlan(BaseModel):
    id: str
    name: str
    description: str
    rpo: str | None = None
    rto: str | None = None


class InfrastructureArchitectOutput(BaseModel):
    cloud_architecture: str = ""
    network_topology: str = ""
    environment_design: str = ""
    environments: list[Environment] = []
    scaling_strategy: str = ""
    scaling_rules: list[ScalingRule] = []
    ha_strategy: str = ""
    disaster_recovery: str = ""
    security_controls: list[SecurityControl] = []
    backup_recovery_plans: list[BackupRecoveryPlan] = []


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class InfrastructureArchitectArtifactResponse(BaseModel):
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


class InfrastructureArchitectRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    frontend_execution_run_id: str | None
    backend_execution_run_id: str | None
    qa_approval_run_id: str | None
    status: InfrastructureArchitectRunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: InfrastructureArchitectArtifactResponse | None = None

    model_config = {"from_attributes": True}


class InfrastructureArchitectRunListResponse(BaseModel):
    items: list[InfrastructureArchitectRunResponse]
    total: int
