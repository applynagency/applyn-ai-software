"""Pydantic schemas for the control plane API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CloudAccountCreate(BaseModel):
    credential_id: str
    display_name: str | None = None


class CloudAccountView(BaseModel):
    id: str
    provider: str
    account_id: str
    display_name: str
    regions: list[str] = Field(default_factory=list)
    health: str
    resource_count: int
    cost_summary: dict | None = None
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None

    model_config = {"from_attributes": True}


class CloudSyncResult(BaseModel):
    sync_run_id: str
    status: str
    resources_total: int


class ClusterCreate(BaseModel):
    credential_id: str
    name: str
    distribution: str = "VANILLA"
    cloud_account_id: str | None = None


class ClusterView(BaseModel):
    id: str
    name: str
    distribution: str
    version: str | None
    api_endpoint: str | None
    health: str
    node_count: int
    namespace_count: int
    last_discovery_at: datetime | None = None

    model_config = {"from_attributes": True}


class ClusterResourceView(BaseModel):
    id: str
    kind: str
    namespace: str | None
    name: str
    health: str
    labels: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict, validation_alias="resource_meta")

    model_config = {"from_attributes": True, "populate_by_name": True}


class OperationCreate(BaseModel):
    kind: str
    cluster_id: str
    namespace: str | None = None
    resource_name: str | None = None
    params: dict = Field(default_factory=dict)


class OperationView(BaseModel):
    id: str
    kind: str
    status: str
    cluster_id: str | None
    namespace: str | None
    resource_name: str | None
    params: dict | None = None
    result: dict | None = None
    error: str | None = None
    integration_readiness: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OperationDecision(BaseModel):
    approved: bool
    comment: str | None = None


class InventoryItemView(BaseModel):
    source: str  # cloud | cluster
    provider: str | None = None
    cloud: str | None = None
    region: str | None = None
    cluster: str | None = None
    namespace: str | None = None
    resource_type: str
    resource_name: str
    owner: str | None = None
    environment: str | None = None
    health: str
    tags: dict = Field(default_factory=dict)


class PolicyFindingView(BaseModel):
    id: str
    policy: str
    severity: str
    resource_kind: str
    resource_name: str
    namespace: str | None
    message: str
    recommendation: str

    model_config = {"from_attributes": True}


class CostView(BaseModel):
    scope_type: str
    scope_id: str
    currency: str
    period_days: int
    total_estimate: float
    breakdown: dict = Field(default_factory=dict)
    opportunities: list = Field(default_factory=list)


class HelmReleaseView(BaseModel):
    name: str
    namespace: str
    chart: str
    version: str
    status: str
    revision: int


class GitOpsAppView(BaseModel):
    engine: str
    name: str
    namespace: str
    sync_status: str
    health: str
    revision: str
    drift: bool


class FederationClusterView(BaseModel):
    id: str
    name: str
    distribution: str
    health: str
    node_count: int = 0
    namespace_count: int = 0


class FederationSummaryView(BaseModel):
    cluster_count: int
    cloud_account_count: int
    inventory_count: int
    providers: list[str] = Field(default_factory=list)
    federation_mode: str
    dr_orchestration: str
    dr_readiness: dict = Field(default_factory=dict)
    recommended_actions: list[str] = Field(default_factory=list)
    clusters: list[FederationClusterView] = Field(default_factory=list)
