from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DeploymentTarget(BaseModel):
    """Connection target for VM (SSH) and Kubernetes deployments.

    Secrets (``private_key`` for VM, ``kubeconfig`` for Kubernetes) are used
    transiently to establish the connection and are NEVER persisted to the
    database. Only non-secret metadata is stored on the deployment run.
    """

    # --- VM (SSH) target — Sprint 34A ---
    host: str | None = None
    port: int = 22
    username: str | None = None
    private_key: str | None = None
    app_port: int = 8000
    deployment_path: str | None = None
    container_name: str | None = None

    # --- Kubernetes target — Sprint 34B ---
    kubeconfig: str | None = None
    namespace: str | None = None
    cluster_name: str | None = None
    ingress_host: str | None = None
    image: str | None = None
    replicas: int = 2


class DeploymentRunRequest(BaseModel):
    requirement_id: str
    approval_run_id: str | None = None
    deployment_provider: str = "AZURE"
    environment: str = "production"
    # Optional: required only when deployment_provider == "VM".
    deployment_target: DeploymentTarget | None = None
    # Sprint 35A: reference a stored, encrypted infrastructure credential.
    # When set, the secret is decrypted at runtime and injected into the
    # transient deployment target — no secret travels in the request body.
    credential_id: str | None = None


class DeploymentRollbackRequest(BaseModel):
    """Optional rollback body. Required for VM/Kubernetes deployments so the
    platform can re-establish the connection (the secret is never stored).

    Sprint 35A: ``credential_id`` may be supplied instead of an inline
    ``deployment_target`` secret."""

    deployment_target: DeploymentTarget | None = None
    credential_id: str | None = None


class DeploymentOutput(BaseModel):
    deployment_provider: str
    deployment_status: str
    live_url: str = ""
    deployment_logs: list[str | dict[str, Any]] = []
    rollback_available: bool = False
    deployment_metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, Any] = {}


class DeploymentLogResponse(BaseModel):
    id: str
    run_id: str
    level: str
    message: str
    log_metadata: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DeploymentLogListResponse(BaseModel):
    items: list[DeploymentLogResponse]
    total: int


class DeploymentArtifactResponse(BaseModel):
    id: str
    run_id: str
    artifact_json: dict[str, Any]
    artifact_markdown: str
    deployment_status: str | None
    deployment_provider: str | None
    live_url: str | None
    validation_score: float | None
    deployer_version: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DeploymentRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    approval_run_id: str | None
    fullstack_assembly_run_id: str | None
    status: str
    deployment_provider: str | None
    live_url: str | None
    environment: str
    rollback_available: bool
    rollback_metadata: dict[str, Any] | None = None
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    validation_score: float | None
    deployer_version: str | None
    artifact: DeploymentArtifactResponse | None = None
    customer_message: str | None = None

    model_config = {"from_attributes": True}


class DeploymentRunListResponse(BaseModel):
    items: list[DeploymentRunResponse]
    total: int
