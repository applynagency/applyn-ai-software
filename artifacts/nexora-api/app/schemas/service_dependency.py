"""Service Dependency / topology schemas (read-only views).

Service dependencies are stored in the single Platform Knowledge Graph
(``KnowledgeGraphEdge``); these schemas are the read-facing projection.
"""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


class DependencyType(str, enum.Enum):
    SYNC = "SYNC"
    ASYNC = "ASYNC"
    DATASTORE = "DATASTORE"
    NETWORK = "NETWORK"
    OTHER = "OTHER"


class DependencyCreate(BaseModel):
    source_service_id: str
    target_service_id: str
    dependency_type: str = Field(default="SYNC", max_length=20)


class ServiceRef(BaseModel):
    id: str
    name: str
    tier: str | None = None
    owner_team: str | None = None


class DependencyEdge(BaseModel):
    id: str
    organization_id: str
    source_service_id: str
    source_name: str | None = None
    target_service_id: str
    target_name: str | None = None
    dependency_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class GraphNode(BaseModel):
    id: str
    name: str
    tier: str | None = None
    owner_team: str | None = None
    dependency_count: int = 0   # out-edges: services this one depends on
    dependent_count: int = 0    # in-edges: services that depend on this one


class DependencyGraph(BaseModel):
    nodes: list[GraphNode] = []
    edges: list[DependencyEdge] = []


class ServiceDependencyView(BaseModel):
    service: ServiceRef
    # Services this service depends on (request flows downstream to them).
    direct_dependencies: list[ServiceRef] = []
    indirect_dependencies: list[ServiceRef] = []
    downstream_services: list[ServiceRef] = []
    # Services that depend on this service (impacted if it fails).
    direct_dependents: list[ServiceRef] = []
    indirect_dependents: list[ServiceRef] = []
    upstream_services: list[ServiceRef] = []
    has_cycle: bool = False


class BlastRadius(BaseModel):
    incident_id: str
    origin_service_id: str | None = None
    origin_service_name: str | None = None
    resolved_from: str  # "assignment" | "monitoring_alert" | "timeline" | "unresolved"
    severity: str | None = None
    direct_impact: list[ServiceRef] = []
    indirect_impact: list[ServiceRef] = []
    affected_services: list[ServiceRef] = []
    affected_count: int = 0
    tier_breakdown: dict[str, int] = {}
    customer_impact_level: str = "LOW"
    customer_impact: str = ""
    summary: str = ""


class BlastRadiusService(BaseModel):
    service: ServiceRef
    dependencies_count: int = 0
    dependents_count: int = 0
    blast_radius_size: int = 0  # transitive dependents
    impact_level: str = "LOW"


class BlastRadiusDashboard(BaseModel):
    total_services: int = 0
    total_dependencies: int = 0
    has_cycles: bool = False
    services: list[BlastRadiusService] = []
    highest_blast_radius: list[BlastRadiusService] = []
