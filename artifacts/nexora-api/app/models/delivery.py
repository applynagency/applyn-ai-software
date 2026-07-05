"""DevOps delivery platform models."""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class SourceConnection(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "dlv_source_connections"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    credential_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deployment_credentials.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    health: Mapped[str] = mapped_column(String(20), nullable=False, default="UNKNOWN")
    repository_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_sync_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class DeliveryRepository(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "dlv_repositories"
    __table_args__ = (Index("ix_dlv_repo_org", "organization_id", "full_name"),)

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    connection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dlv_source_connections.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(128), nullable=False, default="main")
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="private")
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    health: Mapped[str] = mapped_column(String(20), nullable=False, default="HEALTHY")
    stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class DeliveryPipeline(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "dlv_pipelines"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    repository_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("dlv_repositories.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    integration_connection_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("integration_connections.id", ondelete="CASCADE"), nullable=True, index=True,
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class DeliveryPipelineRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "dlv_pipeline_runs"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    pipeline_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dlv_pipelines.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    branch: Mapped[str | None] = mapped_column(String(128), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    logs_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifacts: Mapped[list | None] = mapped_column(JSON, nullable=True)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeliveryEnvironment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "dlv_environments"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cluster_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    freeze_window: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DeliveryArtifact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "dlv_artifacts"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    registry_provider: Mapped[str] = mapped_column(String(30), nullable=False)
    repository: Mapped[str] = mapped_column(String(255), nullable=False)
    tag: Mapped[str] = mapped_column(String(128), nullable=False)
    digest: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    vulnerability_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    promoted_to: Mapped[str | None] = mapped_column(String(64), nullable=True)


class DeliveryRelease(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "dlv_releases"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    repository_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    environment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    release_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rollback_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    dependency_graph: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class DeliveryDeployment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "dlv_deployments"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    release_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("dlv_releases.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    environment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dlv_environments.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    strategy: Mapped[str] = mapped_column(String(20), nullable=False, default="ROLLING")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="QUEUED")
    image_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    traffic_split: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    health_validation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class DeliverySecurityScan(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "dlv_security_scans"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tool: Mapped[str] = mapped_column(String(20), nullable=False)
    target: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="COMPLETED")
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    findings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sbom: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    explain: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


class DeliveryGitOpsApp(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "dlv_gitops_apps"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    cluster_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    engine: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    namespace: Mapped[str] = mapped_column(String(253), nullable=False)
    project: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(30), nullable=False)
    health: Mapped[str] = mapped_column(String(20), nullable=False)
    revision: Mapped[str | None] = mapped_column(String(128), nullable=True)
    auto_sync: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    drift: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    history: Mapped[list | None] = mapped_column(JSON, nullable=True)


class DeliveryOperation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "dlv_operations"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_APPROVAL")
    release_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    deployment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    environment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
