import enum

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class SreApprovalRunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SreStatus(str, enum.Enum):
    SRE_APPROVED = "SRE_APPROVED"
    SRE_APPROVED_WITH_WARNINGS = "SRE_APPROVED_WITH_WARNINGS"
    SRE_REJECTED = "SRE_REJECTED"


class SreApprovalRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sre_approval_runs"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kubernetes_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("kubernetes_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    observability_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("observability_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[SreApprovalRunStatus] = mapped_column(
        String(20), nullable=False, default=SreApprovalRunStatus.PENDING
    )
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)

    artifacts: Mapped[list["SreApprovalArtifact"]] = relationship(
        "SreApprovalArtifact", back_populates="run", cascade="all, delete-orphan"
    )


class SreApprovalArtifact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sre_approval_artifacts"

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sre_approval_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    artifact_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    validation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)

    run: Mapped["SreApprovalRun"] = relationship("SreApprovalRun", back_populates="artifacts")
