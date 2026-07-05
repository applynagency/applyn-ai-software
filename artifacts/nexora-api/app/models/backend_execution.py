import enum

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class BackendExecutionRunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BackendExecutionApprovalStatus(str, enum.Enum):
    BACKEND_APPROVED = "BACKEND_APPROVED"
    BACKEND_APPROVED_WITH_WARNINGS = "BACKEND_APPROVED_WITH_WARNINGS"
    BACKEND_NEEDS_REVIEW = "BACKEND_NEEDS_REVIEW"


class BackendExecutionRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "backend_execution_runs"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    backend_v3_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("backend_v3_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    backend_code_review_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("backend_code_review_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[BackendExecutionRunStatus] = mapped_column(
        String(20), nullable=False, default=BackendExecutionRunStatus.PENDING
    )
    build_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    validation_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    approval_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    executor_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    artifacts: Mapped[list["BackendExecutionArtifact"]] = relationship(
        "BackendExecutionArtifact", back_populates="run", cascade="all, delete-orphan"
    )


class BackendExecutionArtifact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "backend_execution_artifacts"

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("backend_execution_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    artifact_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    build_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    validation_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    approval_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    executor_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    run: Mapped["BackendExecutionRun"] = relationship(
        "BackendExecutionRun", back_populates="artifacts"
    )
