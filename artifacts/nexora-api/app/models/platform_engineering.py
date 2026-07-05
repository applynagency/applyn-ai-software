"""Platform Engineering models (Sprint 64A)."""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class PEIacRepository(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pe_iac_repositories"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    default_branch: Mapped[str] = mapped_column(String(100), nullable=False, default="main")
    working_dir: Mapped[str] = mapped_column(String(255), nullable=False, default=".")
    credential_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class PEIacStack(Base, UUIDMixin, TimestampMixin):
    """IaC workspace/stack with variables and state metadata."""

    __tablename__ = "pe_iac_stacks"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    repository_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("pe_iac_repositories.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    variables: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    secret_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    state_backend: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    outputs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cloud_account_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    cluster_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class PEIacRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pe_iac_runs"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    stack_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pe_iac_stacks.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="QUEUED")
    plan_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    outputs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    logs: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    requested_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PEPlatformTemplate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pe_platform_templates"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    spec: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)


class PEEnvironment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pe_environments"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    template_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("pe_platform_templates.id", ondelete="SET NULL"), nullable=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_APPROVAL")
    stack_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    cluster_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    cloud_account_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    components: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)


class PEProvisionRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pe_provision_runs"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    environment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("pe_environments.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    template_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    distribution: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_APPROVAL")
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    logs: Mapped[str | None] = mapped_column(Text, nullable=True)
    outputs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cluster_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    execution_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    requested_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PESecretReference(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pe_secret_refs"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    backend: Mapped[str] = mapped_column(String(40), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    stack_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    environment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rotation_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_rotated_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class PECatalogItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pe_catalog_items"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    spec: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PECatalogRequest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pe_catalog_requests"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    catalog_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pe_catalog_items.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING_APPROVAL")
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    requested_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    provision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class PEGoldenTemplate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pe_golden_templates"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    spec: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class PEComplianceReport(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pe_compliance_reports"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    grade: Mapped[str] = mapped_column(String(2), nullable=False, default="F")
    findings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    generated_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class PEDriftFinding(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pe_drift_findings"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    resource: Mapped[str] = mapped_column(String(512), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    ai_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    stack_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    cluster_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
