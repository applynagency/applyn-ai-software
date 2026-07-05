import enum

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class DeploymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    DEPLOYING = "DEPLOYING"
    DEPLOYED = "DEPLOYED"
    FAILED = "FAILED"
    ROLLBACK_IN_PROGRESS = "ROLLBACK_IN_PROGRESS"
    ROLLED_BACK = "ROLLED_BACK"


class DeploymentProvider(str, enum.Enum):
    AZURE = "AZURE"
    VM = "VM"
    AWS = "AWS"
    GCP = "GCP"
    KUBERNETES = "KUBERNETES"


class DeploymentRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "deployment_runs"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    approval_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("approval_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    fullstack_assembly_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("fullstack_assembly_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=DeploymentStatus.PENDING.value
    )
    deployment_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    live_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    environment: Mapped[str] = mapped_column(String(50), nullable=False, default="production")
    rollback_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rollback_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    deployer_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    artifacts: Mapped[list["DeploymentArtifact"]] = relationship(
        "DeploymentArtifact", back_populates="run", cascade="all, delete-orphan"
    )
    logs: Mapped[list["DeploymentLog"]] = relationship(
        "DeploymentLog", back_populates="run", cascade="all, delete-orphan"
    )


class DeploymentArtifact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "deployment_artifacts"

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("deployment_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    artifact_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    deployment_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    deployment_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    live_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    validation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    deployer_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    run: Mapped["DeploymentRun"] = relationship("DeploymentRun", back_populates="artifacts")


class DeploymentLog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "deployment_logs"

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("deployment_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="INFO")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    log_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    run: Mapped["DeploymentRun"] = relationship("DeploymentRun", back_populates="logs")
