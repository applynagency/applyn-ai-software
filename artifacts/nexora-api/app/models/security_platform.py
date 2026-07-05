"""Enterprise DevSecOps & Cloud Security Platform models (Sprint 65D)."""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class SecFinding(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sec_findings"
    __table_args__ = (
        UniqueConstraint("organization_id", "fingerprint", name="uq_sec_findings_dedup"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OPEN", index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    resource: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    service: Mapped[str | None] = mapped_column(String(200), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(80), nullable=True)
    owner_team: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cve: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    cvss_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    remediation_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scan_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    related_incident_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    related_deployment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sla_due_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exception_expires_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_system: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    source_record_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    imported_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_breached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SecScanRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sec_scan_runs"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    tool: Mapped[str] = mapped_column(String(40), nullable=False)
    target: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="COMPLETED")
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    gate_decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    execution_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    raw_output_redacted: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)


class SecSbomRef(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sec_sbom_refs"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    scan_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    format: Mapped[str] = mapped_column(String(20), nullable=False, default="cyclonedx")
    target: Mapped[str] = mapped_column(String(512), nullable=False)
    component_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inventory: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class SecException(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sec_exceptions"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    finding_id: Mapped[str] = mapped_column(String(36), ForeignKey("sec_findings.id", ondelete="CASCADE"), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class SecRemediationProposal(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sec_remediation_proposals"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    finding_id: Mapped[str] = mapped_column(String(36), ForeignKey("sec_findings.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    risk: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM")
    impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    rollback_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PROPOSED")
    execution_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    remediation_action_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    execution_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    verification_evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class SecPostureSnapshot(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sec_posture_snapshots"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    posture_score: Mapped[int] = mapped_column(Integer, nullable=False)
    grade: Mapped[str] = mapped_column(String(2), nullable=False)
    breakdown: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    open_critical: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class SecInvestigation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sec_investigations"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    timeline: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    incident_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)


class SecAccessReviewCampaign(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sec_access_review_campaigns"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    scope: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    findings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    due_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class SecProvider(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sec_providers"
    __table_args__ = (
        UniqueConstraint("organization_id", "provider_type", name="uq_sec_providers_org_type"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="unavailable")
    validated_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)


class SecSbomComponent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sec_sbom_components"
    __table_args__ = (
        UniqueConstraint("organization_id", "normalized_key", name="uq_sec_sbom_components_norm"),
    )

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sbom_ref_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sec_sbom_refs.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ecosystem: Mapped[str | None] = mapped_column(String(80), nullable=True)
    license: Mapped[str | None] = mapped_column(String(120), nullable=True)
    purl: Mapped[str | None] = mapped_column(String(512), nullable=True)
    parent_purl: Mapped[str | None] = mapped_column(String(512), nullable=True)
    artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    vuln_finding_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    normalized_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)


class SecBackfillJob(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sec_backfill_jobs"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    counts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class SecSlaPolicy(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sec_sla_policies"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    environment: Mapped[str | None] = mapped_column(String(80), nullable=True)
    due_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    warning_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    owner_team: Mapped[str | None] = mapped_column(String(120), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SecRemediationExecution(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sec_remediation_executions"

    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    proposal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sec_remediation_proposals.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    execution_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    checkpoints: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    rollback_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    verification: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
