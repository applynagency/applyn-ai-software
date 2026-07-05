"""Multi-cloud & Kubernetes control plane models."""

from __future__ import annotations

import enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class CloudAccount(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cp_cloud_accounts"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    credential_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deployment_credentials.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    regions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    health: Mapped[str] = mapped_column(String(20), nullable=False, default="UNKNOWN")
    cost_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    permissions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    last_sync_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    resource_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class CloudSyncRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cp_cloud_sync_runs"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    cloud_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cp_cloud_accounts.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="RUNNING")
    resources_added: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resources_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CloudInventoryResource(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cp_cloud_inventory"
    __table_args__ = (
        Index("ix_cp_cloud_inv_org_provider", "organization_id", "provider"),
    )

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    cloud_account_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    account: Mapped[str] = mapped_column(String(128), nullable=False)
    region: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(256), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    health: Mapped[str] = mapped_column(String(20), nullable=False, default="UNKNOWN")
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


class KubernetesCluster(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cp_kubernetes_clusters"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    credential_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deployment_credentials.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    cloud_account_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("cp_cloud_accounts.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    distribution: Mapped[str] = mapped_column(String(30), nullable=False, default="VANILLA")
    version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    api_endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    context: Mapped[str | None] = mapped_column(String(255), nullable=True)
    health: Mapped[str] = mapped_column(String(20), nullable=False, default="UNKNOWN")
    node_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    namespace_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    labels: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_discovery_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class ClusterDiscoveryRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cp_cluster_discovery_runs"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    cluster_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cp_kubernetes_clusters.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="RUNNING")
    resource_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClusterResource(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cp_cluster_resources"
    __table_args__ = (
        Index("ix_cp_cluster_res_lookup", "organization_id", "cluster_id", "kind", "namespace", "name"),
    )

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    cluster_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    namespace: Mapped[str | None] = mapped_column(String(253), nullable=True)
    name: Mapped[str] = mapped_column(String(253), nullable=False)
    uid: Mapped[str] = mapped_column(String(128), nullable=False)
    labels: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    annotations: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    health: Mapped[str] = mapped_column(String(20), nullable=False, default="UNKNOWN")
    resource_meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


class ControlPlaneOperation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cp_operations"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    cluster_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_APPROVAL")
    namespace: Mapped[str | None] = mapped_column(String(253), nullable=True)
    resource_name: Mapped[str | None] = mapped_column(String(253), nullable=True)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClusterPolicyFinding(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cp_policy_findings"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    cluster_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    policy: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    resource_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_name: Mapped[str] = mapped_column(String(253), nullable=False)
    namespace: Mapped[str | None] = mapped_column(String(253), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ControlPlaneCostSnapshot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "cp_cost_snapshots"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)  # cloud | cluster | namespace
    scope_id: Mapped[str] = mapped_column(String(36), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    period_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    total_estimate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    opportunities: Mapped[list | None] = mapped_column(JSON, nullable=True)


class K8sDiagnosticsBundle(Base, UUIDMixin, TimestampMixin):
    """Collected diagnostics package for a K8s resource (Sprint 65A)."""

    __tablename__ = "cp_k8s_diagnostics"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    cluster_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cp_kubernetes_clusters.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    namespace: Mapped[str | None] = mapped_column(String(253), nullable=True)
    resource_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_name: Mapped[str] = mapped_column(String(253), nullable=False)
    bundle: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    collected_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

