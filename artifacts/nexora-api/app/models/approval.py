import enum

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class ApprovalRunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WorkflowApprovalStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DEPLOYED = "DEPLOYED"


class ApprovalRecommendation(str, enum.Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REVIEW = "REVIEW"


class ApprovalRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "approval_runs"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fullstack_assembly_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("fullstack_assembly_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    frontend_execution_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("frontend_execution_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[ApprovalRunStatus] = mapped_column(
        String(20), nullable=False, default=ApprovalRunStatus.PENDING
    )
    approval_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    processor_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_history: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)

    artifacts: Mapped[list["ApprovalArtifact"]] = relationship(
        "ApprovalArtifact", back_populates="run", cascade="all, delete-orphan"
    )


class ApprovalArtifact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "approval_artifacts"

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("approval_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    artifact_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    approval_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    validation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    processor_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    run: Mapped["ApprovalRun"] = relationship("ApprovalRun", back_populates="artifacts")
