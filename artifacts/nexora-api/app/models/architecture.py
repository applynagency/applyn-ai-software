"""Sprint 46B - Architecture Discovery & Service Map Engine.

Read-only topology discovery. Each ``ArchitectureSnapshot`` is an immutable
point-in-time map built from connected platform signals (service catalog, 44B
dependencies, 42A monitoring providers, deployment runs, 42C SLOs, 43A capacity
metrics). ``ArchitectureNode`` rows are typed entities (services, Kubernetes
workloads, cloud resources, databases, load balancers/ingress, repositories);
``ArchitectureEdge`` rows are typed relationships between them.

Discovery never calls cloud control planes to mutate anything and never modifies
infrastructure - it only reads already-ingested signals.
"""

import enum

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class NodeType(str, enum.Enum):
    SERVICE = "SERVICE"
    KUBERNETES_WORKLOAD = "KUBERNETES_WORKLOAD"
    CLOUD_RESOURCE = "CLOUD_RESOURCE"
    DATABASE = "DATABASE"
    LOAD_BALANCER = "LOAD_BALANCER"
    REPOSITORY = "REPOSITORY"


class EdgeRelationship(str, enum.Enum):
    DEPENDS_ON = "DEPENDS_ON"
    ROUTES_TO = "ROUTES_TO"
    STORES_IN = "STORES_IN"
    RUNS_ON = "RUNS_ON"
    DEPLOYS_TO = "DEPLOYS_TO"


class ArchitectureSnapshot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "architecture_snapshots"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    orphan_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    spof_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_monitoring_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_slo_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ArchitectureNode(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "architecture_nodes"

    snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("architecture_snapshots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String(40), nullable=False, default=NodeType.SERVICE.value)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(60), nullable=True)
    service_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    has_monitoring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_slo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_orphan: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_spof: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dependents_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    depends_on_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    node_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ArchitectureEdge(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "architecture_edges"

    snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("architecture_snapshots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    target_key: Mapped[str] = mapped_column(String(255), nullable=False)
    relationship_type: Mapped[str] = mapped_column(
        String(40), nullable=False, default=EdgeRelationship.DEPENDS_ON.value
    )
