from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.observability_agent import ObservabilityRunStatus


class ObservabilityRunRequest(BaseModel):
    requirement_id: str
    kubernetes_run_id: str | None = None


class GrafanaDashboard(BaseModel):
    id: str
    name: str
    description: str
    panels: list[str] = []


class AlertRule(BaseModel):
    id: str
    name: str
    description: str
    severity: str | None = None
    expression: str | None = None


class LoggingFlow(BaseModel):
    id: str
    name: str
    description: str
    source: str | None = None
    sink: str | None = None


class SLODefinition(BaseModel):
    id: str
    name: str
    description: str
    objective: str | None = None
    sli: str | None = None


class ObservabilityAgentOutput(BaseModel):
    prometheus_configuration: str = ""
    logging_architecture: str = ""
    tracing_architecture: str = ""
    grafana_dashboards: list[GrafanaDashboard] = []
    alert_rules: list[AlertRule] = []
    logging_flows: list[LoggingFlow] = []
    slo_definitions: list[SLODefinition] = []


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class ObservabilityArtifactResponse(BaseModel):
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


class ObservabilityRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    kubernetes_run_id: str | None
    status: ObservabilityRunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: ObservabilityArtifactResponse | None = None

    model_config = {"from_attributes": True}


class ObservabilityRunListResponse(BaseModel):
    items: list[ObservabilityRunResponse]
    total: int
