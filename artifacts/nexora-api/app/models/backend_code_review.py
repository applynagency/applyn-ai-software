import enum

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class BackendCodeReviewRunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BackendApprovalStatus(str, enum.Enum):
    APPROVED = "APPROVED"
    APPROVED_WITH_WARNINGS = "APPROVED_WITH_WARNINGS"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REJECTED = "REJECTED"


class BackendCodeReviewRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "backend_code_review_runs"

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
    status: Mapped[BackendCodeReviewRunStatus] = mapped_column(
        String(20), nullable=False, default=BackendCodeReviewRunStatus.PENDING
    )
    approval_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)

    artifacts: Mapped[list["BackendCodeReviewArtifact"]] = relationship(
        "BackendCodeReviewArtifact", back_populates="run", cascade="all, delete-orphan"
    )


class BackendCodeReviewArtifact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "backend_code_review_artifacts"

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("backend_code_review_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    artifact_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    review_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    approval_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)

    run: Mapped["BackendCodeReviewRun"] = relationship("BackendCodeReviewRun", back_populates="artifacts")
