import enum

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin
from app.models.team import ResponsibilityPriority


class AIAgentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class AIAgentInputType(str, enum.Enum):
    TEXT = "TEXT"
    JSON = "JSON"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    FILE = "FILE"
    LIST = "LIST"


class AIAgentOutputType(str, enum.Enum):
    TEXT = "TEXT"
    JSON = "JSON"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    FILE = "FILE"
    LIST = "LIST"


class AIAgent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_agents"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AIAgentStatus] = mapped_column(
        SAEnum(AIAgentStatus), default=AIAgentStatus.DRAFT, nullable=False
    )
    prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )

    inputs: Mapped[list["AIAgentInput"]] = relationship(
        "AIAgentInput",
        back_populates="agent",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="AIAgentInput.input_name",
    )
    outputs: Mapped[list["AIAgentOutput"]] = relationship(
        "AIAgentOutput",
        back_populates="agent",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="AIAgentOutput.output_name",
    )
    responsibilities: Mapped[list["AIAgentResponsibility"]] = relationship(
        "AIAgentResponsibility",
        back_populates="agent",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    workflow_assignments: Mapped[list["AIAgentWorkflowAssignment"]] = relationship(
        "AIAgentWorkflowAssignment",
        back_populates="agent",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="AIAgentWorkflowAssignment.execution_order",
    )


class AIAgentInput(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_agent_inputs"

    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    input_name: Mapped[str] = mapped_column(String(255), nullable=False)
    input_type: Mapped[AIAgentInputType] = mapped_column(SAEnum(AIAgentInputType), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    agent: Mapped["AIAgent"] = relationship("AIAgent", back_populates="inputs")


class AIAgentOutput(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_agent_outputs"

    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    output_name: Mapped[str] = mapped_column(String(255), nullable=False)
    output_type: Mapped[AIAgentOutputType] = mapped_column(SAEnum(AIAgentOutputType), nullable=False)

    agent: Mapped["AIAgent"] = relationship("AIAgent", back_populates="outputs")


class AIAgentResponsibility(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_agent_responsibilities"

    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[ResponsibilityPriority] = mapped_column(
        SAEnum(ResponsibilityPriority), default=ResponsibilityPriority.MEDIUM, nullable=False
    )

    agent: Mapped["AIAgent"] = relationship("AIAgent", back_populates="responsibilities")


class AIAgentWorkflowAssignment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_agent_workflow_assignments"

    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_stage_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_stages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
    )
    execution_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    agent: Mapped["AIAgent"] = relationship("AIAgent", back_populates="workflow_assignments")
    stage: Mapped["WorkflowStage"] = relationship("WorkflowStage", lazy="selectin")  # noqa: F821
    team: Mapped["Team"] = relationship("Team", lazy="selectin")  # noqa: F821
