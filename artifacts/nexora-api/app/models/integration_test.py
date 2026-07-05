import enum

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class IntegrationTestRunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IntegrationTestRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integration_test_runs"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    frontend_execution_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("frontend_execution_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    backend_execution_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("backend_execution_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    unit_test_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("unit_test_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[IntegrationTestRunStatus] = mapped_column(
        String(20), nullable=False, default=IntegrationTestRunStatus.PENDING
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

    artifacts: Mapped[list["IntegrationTestArtifact"]] = relationship(
        "IntegrationTestArtifact", back_populates="run", cascade="all, delete-orphan"
    )


class IntegrationTestArtifact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integration_test_artifacts"

    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("integration_test_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    artifact_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    validation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)

    run: Mapped["IntegrationTestRun"] = relationship(
        "IntegrationTestRun", back_populates="artifacts"
    )
