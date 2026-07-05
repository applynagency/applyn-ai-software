from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.kubernetes_agent import KubernetesRunStatus


class KubernetesRunRequest(BaseModel):
    requirement_id: str
    cicd_run_id: str | None = None


class K8sDeployment(BaseModel):
    id: str
    name: str
    description: str
    image: str | None = None
    replicas: int | None = None


class K8sService(BaseModel):
    id: str
    name: str
    description: str
    service_type: str | None = None
    port: int | None = None


class K8sIngress(BaseModel):
    id: str
    name: str
    description: str
    host: str | None = None
    path: str | None = None


class K8sHorizontalPodAutoscaler(BaseModel):
    id: str
    name: str
    description: str
    min_replicas: int | None = None
    max_replicas: int | None = None
    target_metric: str | None = None


class K8sConfig(BaseModel):
    id: str
    name: str
    description: str
    kind: str | None = None


class K8sNetworkPolicy(BaseModel):
    id: str
    name: str
    description: str


class K8sEnvironmentOverlay(BaseModel):
    id: str
    name: str
    description: str
    environment: str | None = None


class KubernetesAgentOutput(BaseModel):
    cluster_overview: str = ""
    deployments: list[K8sDeployment] = []
    services: list[K8sService] = []
    ingresses: list[K8sIngress] = []
    hpas: list[K8sHorizontalPodAutoscaler] = []
    configmaps_secrets: list[K8sConfig] = []
    network_policies: list[K8sNetworkPolicy] = []
    environment_overlays: list[K8sEnvironmentOverlay] = []


class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    errors: list[str] = []
    counts: dict[str, int] = {}


class KubernetesArtifactResponse(BaseModel):
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


class KubernetesRunResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    requirement_id: str
    cicd_run_id: str | None
    status: KubernetesRunStatus
    created_by: str
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    tokens_used: int | None
    validation_score: float | None
    prompt_version: str | None
    model_used: str | None
    artifact: KubernetesArtifactResponse | None = None

    model_config = {"from_attributes": True}


class KubernetesRunListResponse(BaseModel):
    items: list[KubernetesRunResponse]
    total: int
