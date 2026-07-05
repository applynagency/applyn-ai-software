"""GA readiness models (Sprint 64A)."""

from __future__ import annotations

import enum

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, DateTime

from app.database.base import Base, TimestampMixin, UUIDMixin


class InstallStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BackupStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


class ReleaseChannel(str, enum.Enum):
    STABLE = "stable"
    PREVIEW = "preview"
    DEVELOPMENT = "development"


class GAInstallRun(Base, UUIDMixin, TimestampMixin):
    """First-run setup / readiness validation run."""

    __tablename__ = "ga_install_runs"

    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=InstallStatus.PENDING.value)
    version: Mapped[str] = mapped_column(String(40), nullable=False, default="1.0.0")
    checks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    readiness_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    readiness_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sample_data_loaded: Mapped[bool] = mapped_column(nullable=False, default=False)
    admin_bootstrapped: Mapped[bool] = mapped_column(nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class GABackupRecord(Base, UUIDMixin, TimestampMixin):
    """Backup catalog entry with verification and retention metadata."""

    __tablename__ = "ga_backup_records"

    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    encrypted: Mapped[bool] = mapped_column(nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=BackupStatus.PENDING.value)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    verified_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    schedule_cadence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    __table_args__ = (
        Index("ix_ga_backup_org_created", "organization_id", "created_at"),
    )


class GARestoreHistory(Base, UUIDMixin, TimestampMixin):
    """Restore wizard execution history."""

    __tablename__ = "ga_restore_history"

    backup_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ga_backup_records.id", ondelete="CASCADE"), nullable=False)
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    initiated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_ga_restore_backup", "backup_id"),
    )


class GASupportToken(Base, UUIDMixin, TimestampMixin):
    """Time-limited diagnostics / support-mode token (hash stored only)."""

    __tablename__ = "ga_support_tokens"

    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(40), nullable=False, default="diagnostics")
    read_only: Mapped[bool] = mapped_column(nullable=False, default=True)
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    revoked_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    audit_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class GAComplianceReport(Base, UUIDMixin, TimestampMixin):
    """Compliance evidence report (never fabricates controls)."""

    __tablename__ = "ga_compliance_reports"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    framework: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)
    gaps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    readiness_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        Index("ix_ga_compliance_org_fw", "organization_id", "framework"),
    )


class GACustomerSuccessProgress(Base, UUIDMixin, TimestampMixin):
    """Onboarding milestone and adoption tracking."""

    __tablename__ = "ga_customer_success"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True)
    milestones: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    adoption_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recommendations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    setup_complete: Mapped[bool] = mapped_column(nullable=False, default=False)
