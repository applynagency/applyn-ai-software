import enum

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class FrontendV3RunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FrontendV3Run(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "frontend_v3_runs"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    frontend_v2_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("frontend_v2_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[FrontendV3RunStatus] = mapped_column(
        String(20), nullable=False, default=FrontendV3RunStatus.PENDING
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

    artifacts: Mapped[list["FrontendV3Artifact"]] = relationship(
        "FrontendV3Artifact", back_populates="run", cascade="all, delete-orphan"
    )


class FrontendV3Artifact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "frontend_v3_artifacts"

    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("frontend_v3_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    artifact_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    validation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)

    run: Mapped["FrontendV3Run"] = relationship("FrontendV3Run", back_populates="artifacts")
