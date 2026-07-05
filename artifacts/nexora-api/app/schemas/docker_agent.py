from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.docker_agent import DockerAgentRunStatus


class DockerAgentRunRequest(BaseModel):
    requirement_id: str
    infrastructure_architect_run_id: str | None = None


class DockerAgentOutput(BaseModel):
    dockerfile_strategy: str = ""
    docker_compose: str = ""
    container_topology: str = ""
    runtime_configuration: str = ""
    image_optimization: str = ""
    security_hardening: str = ""


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class DockerAgentArtifactResponse(BaseModel):
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


class DockerAgentRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    infrastructure_architect_run_id: str | None
    status: DockerAgentRunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: DockerAgentArtifactResponse | None = None

    model_config = {"from_attributes": True}


class DockerAgentRunListResponse(BaseModel):
    items: list[DockerAgentRunResponse]
    total: int
