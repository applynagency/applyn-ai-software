"""Sprint 58A.2.1 — Universal Discovery Framework models.

Upgrades the infrastructure-only discovery pipeline (58A.2) into a provider-aware
Universal Discovery Framework so EVERY connected integration participates in
discovery — not just AWS / Azure / Kubernetes.

Models (strictly additive; read-only w.r.t. customer systems; no secrets stored):

* ``DiscoveredAsset`` — the Universal Resource Model. One row per discovered
  object across every domain (Infrastructure, Application, Repository,
  Deployment, Collaboration, Business). This is the single source of truth the
  AI consumes.
* ``KnowledgeGraphNode`` / ``KnowledgeGraphEdge`` — the Platform Knowledge Graph
  derived from discovered assets and their cross-provider relationships
  (Repository → Deployment → Service → Namespace → Pod → Incident, and
  Service → Jira Component → GitHub Repository → Slack Channel → Team → Owner).
* ``UniversalDiscoveryEvent`` — emitted change events for every provider
  (RESOURCE_ADDED/UPDATED/REMOVED, RELATIONSHIP_ADDED/REMOVED, SERVICE_CHANGED,
  OWNERSHIP_CHANGED, DEPLOYMENT_CHANGED).

The existing ``DiscoveryScanRun`` (58A.2) is reused to track a universal scan's
progress, so no second scan-run table is introduced.
"""

import enum

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class DiscoveryDomain(str, enum.Enum):
    """The discovery domain a resource belongs to. A provider may register more
    than one domain (e.g. GitHub → REPOSITORY + DEPLOYMENT)."""

    INFRASTRUCTURE = "INFRASTRUCTURE"
    APPLICATION = "APPLICATION"
    REPOSITORY = "REPOSITORY"
    DEPLOYMENT = "DEPLOYMENT"
    COLLABORATION = "COLLABORATION"
    BUSINESS = "BUSINESS"


class UniversalEventType(str, enum.Enum):
    RESOURCE_ADDED = "RESOURCE_ADDED"
    RESOURCE_UPDATED = "RESOURCE_UPDATED"
    RESOURCE_REMOVED = "RESOURCE_REMOVED"
    RELATIONSHIP_ADDED = "RELATIONSHIP_ADDED"
    RELATIONSHIP_REMOVED = "RELATIONSHIP_REMOVED"
    SERVICE_CHANGED = "SERVICE_CHANGED"
    OWNERSHIP_CHANGED = "OWNERSHIP_CHANGED"
    DEPLOYMENT_CHANGED = "DEPLOYMENT_CHANGED"


class DiscoveredAsset(Base, UUIDMixin, TimestampMixin):
    """The Universal Resource Model — one normalized row per discovered object.

    Uniqueness within a tenant is (provider, domain, resource_type, resource_id);
    re-scanning the same object updates the existing row (upsert) rather than
    creating duplicates, so ``first_seen_at``/``last_seen_at`` give a stable
    lifetime and the diff engine can detect ADD / UPDATE / REMOVE.
    """

    __tablename__ = "discovered_assets"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scan_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("discovery_scan_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(60), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(512), nullable=False)
    resource_name: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    parent_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    account: Mapped[str | None] = mapped_column(String(255), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(120), nullable=True)
    health: Mapped[str] = mapped_column(String(20), nullable=False, default="UNKNOWN")
    status: Mapped[str | None] = mapped_column(String(60), nullable=True)
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    relationships: Mapped[list | None] = mapped_column(JSON, nullable=True)
    asset_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_created_at: Mapped[str | None] = mapped_column(String(60), nullable=True)
    source_updated_at: Mapped[str | None] = mapped_column(String(60), nullable=True)
    fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class KnowledgeGraphNode(Base, UUIDMixin, TimestampMixin):
    """A node in the Platform Knowledge Graph — single source of truth for AI."""

    __tablename__ = "knowledge_graph_nodes"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_key: Mapped[str] = mapped_column(String(600), nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String(60), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(30), nullable=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    asset_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("discovered_assets.id", ondelete="SET NULL"), nullable=True
    )
    node_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_seen_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class KnowledgeGraphEdge(Base, UUIDMixin, TimestampMixin):
    """A directed relationship between two knowledge-graph nodes."""

    __tablename__ = "knowledge_graph_edges"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_key: Mapped[str] = mapped_column(String(600), nullable=False, index=True)
    target_key: Mapped[str] = mapped_column(String(600), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(60), nullable=False)
    edge_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_seen_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Composite indexes keep adjacency loading (filter by org) and edge lookups
    # fast so traversal over the single graph stays O(V+E).
    __table_args__ = (
        Index("ix_kg_edges_org_source", "organization_id", "source_key"),
        Index("ix_kg_edges_org_target", "organization_id", "target_key"),
    )


class UniversalDiscoveryEvent(Base, UUIDMixin, TimestampMixin):
    """An emitted discovery change event (timeline + downstream reactions)."""

    __tablename__ = "universal_discovery_events"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scan_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("discovery_scan_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(30), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    resource_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
