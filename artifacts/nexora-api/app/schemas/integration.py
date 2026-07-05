"""Sprint 47B - Integration Marketplace schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IntegrationEnrichment(BaseModel):
    live_data: bool = False
    pipeline_sync: bool = False
    gitops_sync: bool = False
    discovery: bool = False
    alert_ingest: bool = False
    unlocks_now: list[str] = []
    unlocks_live: list[str] = []
    pages: list[str] = []


class CatalogItem(BaseModel):
    integration_key: str
    name: str
    category: str
    description: str | None = None
    auth_type: str
    required_fields: list[str] = []
    capabilities: list[str] = []
    docs_url: str | None = None
    is_active: bool = True
    # per-org connection rollup
    connected: bool = False
    connection_count: int = 0
    status: str | None = None
    enrichment: IntegrationEnrichment | None = None


class ConnectRequest(BaseModel):
    integration_key: str
    name: str | None = None
    credentials: dict = Field(default_factory=dict)


class UpdateConnectionCredentialsRequest(BaseModel):
    name: str | None = None
    credentials: dict | None = None


class VerifyRequest(BaseModel):
    connection_id: str


class CheckView(BaseModel):
    name: str
    passed: bool
    message: str


class ConnectionView(BaseModel):
    id: str
    organization_id: str
    integration_key: str
    name: str
    status: str
    health: str
    readiness_score: int = 0
    permissions_granted: list[str] = []
    checks: list[CheckView] = []
    last_verified_at: datetime | None = None
    last_sync_at: datetime | None = None
    created_at: datetime
    enrichment: IntegrationEnrichment | None = None
    # Sprint 58A.1 — real verification surface (optional; populated after verify).
    connection_status: str | None = None
    provider_version: str | None = None
    latency_ms: int | None = None
    provider_identity: dict = {}
    warnings: list[str] = []
    errors: list[str] = []
    confidence: int | None = None

    model_config = {"from_attributes": True}


class VerifyResponse(BaseModel):
    connection_id: str
    integration_key: str
    verified: bool
    status: str
    health: str
    readiness_score: int
    checks: list[CheckView] = []
    permissions_granted: list[str] = []
    guidance: str
    # Sprint 58A.1 — real verification result (additive; backward compatible).
    connection_status: str | None = None
    latency_ms: int | None = None
    provider_version: str | None = None
    verified_at: datetime | None = None
    provider_identity: dict = {}
    permissions: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    confidence: int | None = None


class MarketplaceSummary(BaseModel):
    supported: int = 0
    connected: int = 0
    verified: int = 0
    needs_attention: int = 0
    disconnected: int = 0
    live_capable: int = 0
    live_synced: int = 0


class SyncResponse(BaseModel):
    connection_id: str
    integration_key: str
    pipelines_synced: int = 0
    runs_synced: int = 0
    synced_at: datetime | None = None


class HealthBoardRow(BaseModel):
    connection_id: str
    integration_key: str
    name: str
    status: str
    health: str
    readiness_score: int = 0
    live_data: bool = False
    pipeline_sync: bool = False
    gitops_sync: bool = False
    discovery: bool = False
    alert_ingest: bool = False
    last_sync_at: datetime | None = None
    last_verified_at: datetime | None = None
    alerts_24h: int = 0
    firing_alerts: int = 0
    permissions_granted: list[str] = []


class MarketplaceResponse(BaseModel):
    summary: MarketplaceSummary
    integrations: list[CatalogItem] = []
