import enum

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class FullstackAssemblyRunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AssemblyStatus(str, enum.Enum):
    ASSEMBLY_APPROVED = "ASSEMBLY_APPROVED"
    ASSEMBLY_APPROVED_WITH_WARNINGS = "ASSEMBLY_APPROVED_WITH_WARNINGS"
    ASSEMBLY_NEEDS_REVIEW = "ASSEMBLY_NEEDS_REVIEW"


class FullstackAssemblyRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "fullstack_assembly_runs"

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
    status: Mapped[FullstackAssemblyRunStatus] = mapped_column(
        String(20), nullable=False, default=FullstackAssemblyRunStatus.PENDING
    )
    assembly_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    assembler_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    artifacts: Mapped[list["FullstackAssemblyArtifact"]] = relationship(
        "FullstackAssemblyArtifact", back_populates="run", cascade="all, delete-orphan"
    )


class FullstackAssemblyArtifact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "fullstack_assembly_artifacts"

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("fullstack_assembly_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    artifact_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    assembly_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    validation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    assembler_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    run: Mapped["FullstackAssemblyRun"] = relationship(
        "FullstackAssemblyRun", back_populates="artifacts"
    )
