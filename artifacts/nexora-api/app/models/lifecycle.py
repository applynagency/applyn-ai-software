import enum

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class RegenerationScope(str, enum.Enum):
    FRONTEND_ONLY = "FRONTEND_ONLY"
    BACKEND_ONLY = "BACKEND_ONLY"
    FULL_STACK = "FULL_STACK"


class RegenerationRunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ApplicationVersionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    RELEASED = "RELEASED"
    SUPERSEDED = "SUPERSEDED"


class ApplicationVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "application_versions"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ApplicationVersionStatus.DRAFT.value
    )
    release_date: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    deployment_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approval_history: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )

    release_entries: Mapped[list["ReleaseHistory"]] = relationship(
        "ReleaseHistory", back_populates="application_version", cascade="all, delete-orphan"
    )


class RegenerationRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "regeneration_runs"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("application_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_version: Mapped[str] = mapped_column(String(20), nullable=False)
    scope: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RegenerationScope.FULL_STACK.value
    )
    change_request_title: Mapped[str] = mapped_column(String(255), nullable=False)
    change_request_description: Mapped[str] = mapped_column(Text, nullable=False)
    impact_analysis: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    execution_plan: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RegenerationRunStatus.PENDING.value
    )
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_effort_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    executed_agents: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    artifacts: Mapped[list["RegenerationArtifact"]] = relationship(
        "RegenerationArtifact", back_populates="run", cascade="all, delete-orphan"
    )
    release_entries: Mapped[list["ReleaseHistory"]] = relationship(
        "ReleaseHistory", back_populates="regeneration_run", cascade="all, delete-orphan"
    )


class RegenerationArtifact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "regeneration_artifacts"

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("regeneration_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    artifact_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    artifact_markdown: Mapped[str] = mapped_column(Text, nullable=False)

    run: Mapped["RegenerationRun"] = relationship("RegenerationRun", back_populates="artifacts")


class ReleaseHistory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "release_history"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("application_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    regeneration_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("regeneration_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    fullstack_assembly_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("fullstack_assembly_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    approval_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("approval_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    deployment_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("deployment_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    release_date: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    deployment_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approval_history: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    application_version: Mapped[ApplicationVersion] = relationship(
        "ApplicationVersion", back_populates="release_entries"
    )
    regeneration_run: Mapped[RegenerationRun | None] = relationship(
        "RegenerationRun", back_populates="release_entries"
    )
