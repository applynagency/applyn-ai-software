import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class ExecutionStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"


class ExecutionAgentKind(str, enum.Enum):
    INTERNAL = "INTERNAL"
    CUSTOM = "CUSTOM"


class WorkflowExecution(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_executions"

    # Hot list paths: an org's executions (optionally by workflow), newest first.
    __table_args__ = (
        Index(
            "ix_workflow_executions_org_status_created",
            "organization_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_workflow_executions_org_workflow_created",
            "organization_id",
            "workflow_id",
            "created_at",
        ),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        SAEnum(ExecutionStatus), default=ExecutionStatus.PENDING, nullable=False
    )
    started_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_plan_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    stages: Mapped[list["WorkflowExecutionStage"]] = relationship(
        "WorkflowExecutionStage",
        back_populates="execution",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="WorkflowExecutionStage.sequence",
    )


class WorkflowExecutionStage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_execution_stages"

    workflow_execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_stage_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_stages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[ExecutionStatus] = mapped_column(
        SAEnum(ExecutionStatus), default=ExecutionStatus.PENDING, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    execution: Mapped["WorkflowExecution"] = relationship("WorkflowExecution", back_populates="stages")
    agents: Mapped[list["WorkflowExecutionAgent"]] = relationship(
        "WorkflowExecutionAgent",
        back_populates="stage",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="WorkflowExecutionAgent.execution_order",
    )


class WorkflowExecutionAgent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_execution_agents"

    workflow_execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_execution_stage_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_execution_stages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_kind: Mapped[ExecutionAgentKind] = mapped_column(SAEnum(ExecutionAgentKind), nullable=False)
    internal_agent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    custom_agent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ai_agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    team_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(255), nullable=False)
    team_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    execution_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[ExecutionStatus] = mapped_column(
        SAEnum(ExecutionStatus), default=ExecutionStatus.PENDING, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    log_messages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    stage: Mapped["WorkflowExecutionStage"] = relationship(
        "WorkflowExecutionStage", back_populates="agents"
    )
