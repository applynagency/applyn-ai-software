"""Sprint 46B - Architecture Discovery & Service Map schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NodeView(BaseModel):
    node_key: str
    node_type: str
    name: str
    provider: str | None = None
    environment: str | None = None
    service_name: str | None = None
    has_monitoring: bool = False
    has_slo: bool = False
    is_orphan: bool = False
    is_spof: bool = False
    dependents_count: int = 0
    depends_on_count: int = 0
    metadata: dict = {}


class EdgeView(BaseModel):
    source: str
    target: str
    relationship: str


class RiskAreas(BaseModel):
    orphan_services: list[str] = []
    single_points_of_failure: list[str] = []
    missing_monitoring: list[str] = []
    missing_slo: list[str] = []


class SnapshotResponse(BaseModel):
    id: str
    organization_id: str
    node_count: int
    edge_count: int
    orphan_count: int
    spof_count: int
    missing_monitoring_count: int
    missing_slo_count: int
    summary: str | None = None
    nodes: list[NodeView] = []
    edges: list[EdgeView] = []
    risk_areas: RiskAreas = RiskAreas()
    node_type_counts: dict = {}
    created_at: datetime

    model_config = {"from_attributes": True}


class SnapshotSummary(BaseModel):
    id: str
    node_count: int
    edge_count: int
    orphan_count: int
    spof_count: int
    missing_monitoring_count: int
    missing_slo_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ArchitectureTrendPoint(BaseModel):
    date: str
    node_count: int
    edge_count: int
    spof_count: int
    missing_monitoring_count: int


class ArchitectureDashboard(BaseModel):
    latest: SnapshotResponse | None = None
    snapshots_count: int = 0
    trend: list[ArchitectureTrendPoint] = []


class DiscoverRequest(BaseModel):
    note: str | None = None
