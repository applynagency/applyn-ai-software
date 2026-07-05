"""Sprint 58A.2.1 — Universal Discovery Framework schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.discovery_pipeline import ScanProgressView


class UniversalAssetView(BaseModel):
    id: str
    provider: str
    domain: str
    resource_type: str
    resource_id: str
    resource_name: str
    display_name: str | None = None
    parent_id: str | None = None
    owner: str | None = None
    region: str | None = None
    account: str | None = None
    environment: str | None = None
    health: str = "UNKNOWN"
    status: str | None = None
    tags: dict = Field(default_factory=dict)
    relationships: list[dict] = Field(default_factory=list)
    asset_metadata: dict = Field(default_factory=dict)
    source_created_at: str | None = None
    source_updated_at: str | None = None
    last_seen_at: datetime | None = None

    model_config = {"from_attributes": True}

    @field_validator("tags", "asset_metadata", mode="before")
    @classmethod
    def _none_to_dict(cls, v):
        return v or {}

    @field_validator("relationships", mode="before")
    @classmethod
    def _none_to_list(cls, v):
        return v or []


class DiscoveryEventView(BaseModel):
    id: str
    event_type: str
    provider: str
    domain: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    resource_name: str | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("details", mode="before")
    @classmethod
    def _none_to_dict(cls, v):
        return v or {}


class GraphNodeView(BaseModel):
    node_key: str
    node_type: str
    provider: str | None = None
    domain: str | None = None
    name: str
    display_name: str | None = None
    node_metadata: dict = Field(default_factory=dict)

    model_config = {"from_attributes": True}

    @field_validator("node_metadata", mode="before")
    @classmethod
    def _none_to_dict(cls, v):
        return v or {}


class GraphEdgeView(BaseModel):
    source_key: str
    target_key: str
    relationship_type: str

    model_config = {"from_attributes": True}


class KnowledgeGraphView(BaseModel):
    nodes: list[GraphNodeView] = Field(default_factory=list)
    edges: list[GraphEdgeView] = Field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0


class ProviderDomainStatus(BaseModel):
    """One connected provider's discovery status — skipped providers are never
    hidden; they show with ``skipped`` / a reason instead."""

    provider: str
    connection_name: str
    domains: list[str] = Field(default_factory=list)
    asset_count: int = 0
    supported: bool = True
    note: str | None = None


class DomainSummary(BaseModel):
    domain: str
    asset_count: int = 0
    providers: list[str] = Field(default_factory=list)
    resource_type_counts: dict = Field(default_factory=dict)


class UniversalDiscoverySummary(BaseModel):
    total_assets: int = 0
    domains: list[DomainSummary] = Field(default_factory=list)
    providers: list[ProviderDomainStatus] = Field(default_factory=list)
    provider_counts: dict = Field(default_factory=dict)
    node_count: int = 0
    edge_count: int = 0
    latest_scan: ScanProgressView | None = None


class UniversalSyncRequest(BaseModel):
    providers: list[str] | None = None


class UniversalSyncResponse(BaseModel):
    scan: ScanProgressView
    summary: UniversalDiscoverySummary
    events: list[DiscoveryEventView] = Field(default_factory=list)


class AIContextResponse(BaseModel):
    """The discovered context the AI consumes for a service / incident."""

    subject: str
    matched_assets: list[UniversalAssetView] = Field(default_factory=list)
    repositories: list[UniversalAssetView] = Field(default_factory=list)
    deployments: list[UniversalAssetView] = Field(default_factory=list)
    services: list[UniversalAssetView] = Field(default_factory=list)
    owners: list[str] = Field(default_factory=list)
    slack_channels: list[UniversalAssetView] = Field(default_factory=list)
    teams_channels: list[UniversalAssetView] = Field(default_factory=list)
    jira_projects: list[UniversalAssetView] = Field(default_factory=list)
    related: list[UniversalAssetView] = Field(default_factory=list)
