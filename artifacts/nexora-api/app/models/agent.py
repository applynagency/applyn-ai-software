import enum

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class AgentType(str, enum.Enum):
    PRODUCT_OWNER = "product_owner"
    TECH_LEAD = "tech_lead"
    QA_ENGINEER = "qa_engineer"
    SCRUM_MASTER = "scrum_master"


class AgentRunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agent_runs"

    agent_type: Mapped[AgentType] = mapped_column(
        SAEnum(AgentType), nullable=False
    )
    status: Mapped[AgentRunStatus] = mapped_column(
        SAEnum(AgentRunStatus), default=AgentRunStatus.QUEUED, nullable=False
    )
    requirement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    triggered_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)

    requirement: Mapped["Requirement"] = relationship("Requirement", back_populates="agent_runs")  # noqa: F821
    outputs: Mapped[list["AgentOutput"]] = relationship(
        "AgentOutput", back_populates="agent_run", lazy="selectin"
    )


class AgentOutput(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agent_outputs"

    agent_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    output_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    agent_run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="outputs")
