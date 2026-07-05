from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.cicd_agent import CicdRunStatus


class CicdRunRequest(BaseModel):
    requirement_id: str
    docker_agent_run_id: str | None = None


class CicdAgentOutput(BaseModel):
    github_actions: str = ""
    azure_devops: str = ""
    gitlab_ci: str = ""
    build_pipeline: str = ""
    release_pipeline: str = ""
    rollback_strategy: str = ""


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class CicdArtifactResponse(BaseModel):
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


class CicdRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    docker_agent_run_id: str | None
    status: CicdRunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: CicdArtifactResponse | None = None

    model_config = {"from_attributes": True}


class CicdRunListResponse(BaseModel):
    items: list[CicdRunResponse]
    total: int
