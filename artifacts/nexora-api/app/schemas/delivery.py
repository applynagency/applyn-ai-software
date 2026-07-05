"""Pydantic schemas for the delivery platform API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SourceConnectionCreate(BaseModel):
    credential_id: str
    display_name: str | None = None


class SourceConnectionView(BaseModel):
    id: str
    provider: str
    account_id: str
    display_name: str
    health: str
    repository_count: int
    last_sync_at: datetime | None = None

    model_config = {"from_attributes": True}


class RepositoryView(BaseModel):
    id: str
    name: str
    full_name: str
    default_branch: str
    visibility: str
    url: str | None
    language: str | None
    health: str
    stats: dict | None = None

    model_config = {"from_attributes": True}


class PipelineView(BaseModel):
    id: str
    provider: str
    name: str
    status: str
    repository_id: str | None

    model_config = {"from_attributes": True}


class PipelineRunView(BaseModel):
    id: str
    pipeline_id: str
    external_id: str
    status: str
    branch: str | None
    commit_sha: str | None
    duration_seconds: int | None
    url: str | None
    logs_preview: str | None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class EnvironmentView(BaseModel):
    id: str
    tier: str
    name: str
    sort_order: int
    requires_approval: bool
    cluster_id: str | None

    model_config = {"from_attributes": True}


class ArtifactView(BaseModel):
    id: str
    registry_provider: str
    repository: str
    tag: str
    digest: str
    size_bytes: int
    vulnerability_summary: dict | None = None
    promoted_to: str | None = None

    model_config = {"from_attributes": True}


class ReleaseCreate(BaseModel):
    version: str
    repository_id: str | None = None
    artifact_id: str | None = None
    environment_id: str | None = None
    release_notes: str | None = None


class ReleaseView(BaseModel):
    id: str
    version: str
    status: str
    risk_score: float | None
    release_notes: str | None
    rollback_plan: str | None
    repository_id: str | None
    artifact_id: str | None
    environment_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DeploymentCreate(BaseModel):
    environment_id: str
    release_id: str | None = None
    strategy: str = "ROLLING"
    image_ref: str | None = None


class DeploymentView(BaseModel):
    id: str
    environment_id: str
    release_id: str | None
    strategy: str
    status: str
    image_ref: str | None
    traffic_split: dict | None = None
    health_validation: dict | None = None
    error: str | None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DeploymentListResponse(BaseModel):
    items: list[DeploymentView]
    total: int
    offset: int
    limit: int


class DeploymentIncidentLink(BaseModel):
    id: str
    title: str | None = None
    status: str | None = None
    severity: str | None = None
    created_at: datetime | None = None
    link_source: str | None = None


class DeploymentDetailView(BaseModel):
    deployment: DeploymentView
    environment_name: str | None = None
    environment_tier: str | None = None
    release: ReleaseView | None = None
    linked_operations: list["OperationView"] = Field(default_factory=list)
    linked_incidents: list[DeploymentIncidentLink] = Field(default_factory=list)
    rollback_plan: str | None = None


class SecurityScanRequest(BaseModel):
    tool: str
    target: str
    artifact_id: str | None = None


class SecurityScanView(BaseModel):
    id: str
    tool: str
    target: str
    status: str
    summary: dict | None = None
    findings: list | None = None
    sbom: dict | None = None
    explain: str | None = None

    model_config = {"from_attributes": True}


class GitOpsAppView(BaseModel):
    id: str
    engine: str
    name: str
    namespace: str
    sync_status: str
    health: str
    revision: str | None
    drift: bool
    auto_sync: bool

    model_config = {"from_attributes": True}


class OperationCreate(BaseModel):
    kind: str
    release_id: str | None = None
    deployment_id: str | None = None
    environment_id: str | None = None
    params: dict = Field(default_factory=dict)


class OperationDecision(BaseModel):
    approved: bool
    comment: str | None = None


class OperationView(BaseModel):
    id: str
    kind: str
    status: str
    release_id: str | None
    deployment_id: str | None
    environment_id: str | None
    params: dict | None = None
    result: dict | None = None
    error: str | None = None
    integration_readiness: dict | None = None
    requested_by: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    executed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DoraMetricsView(BaseModel):
    deployment_frequency_per_day: float
    lead_time_hours: float
    change_failure_rate_percent: float
    mttr_hours: float
    window_days: int
    evidence: dict


class DashboardView(BaseModel):
    repositories: int
    pipelines: int
    deployments: int
    releases: int
    environments: int
    gitops_apps: int
    security_scans: int
    pending_operations: int
    dora: DoraMetricsView
