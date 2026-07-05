import enum

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class WorkflowStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class StageType(str, enum.Enum):
    PLANNING = "PLANNING"
    DESIGN = "DESIGN"
    DEVELOPMENT = "DEVELOPMENT"
    QUALITY = "QUALITY"
    APPROVAL = "APPROVAL"
    DEPLOYMENT = "DEPLOYMENT"
    CUSTOM = "CUSTOM"


class WorkflowRuleType(str, enum.Enum):
    HEALTHCARE_COMPLIANCE = "HEALTHCARE_COMPLIANCE"
    FINANCIAL_SECURITY = "FINANCIAL_SECURITY"
    FINANCIAL_RISK = "FINANCIAL_RISK"
    PRODUCTION_APPROVAL = "PRODUCTION_APPROVAL"
    CUSTOM = "CUSTOM"


class Workflow(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflows"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[WorkflowStatus] = mapped_column(
        SAEnum(WorkflowStatus), default=WorkflowStatus.DRAFT, nullable=False
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )

    stages: Mapped[list["WorkflowStage"]] = relationship(
        "WorkflowStage",
        back_populates="workflow",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="WorkflowStage.sequence",
    )
    rules: Mapped[list["WorkflowRule"]] = relationship(
        "WorkflowRule",
        back_populates="workflow",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class WorkflowStage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_stages"

    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    stage_type: Mapped[StageType] = mapped_column(SAEnum(StageType), nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="stages")
    team_assignments: Mapped[list["WorkflowStageTeam"]] = relationship(
        "WorkflowStageTeam",
        back_populates="stage",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="WorkflowStageTeam.execution_order",
    )


class WorkflowStageTeam(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_stage_teams"
    __table_args__ = (
        UniqueConstraint("workflow_stage_id", "team_id", name="uq_workflow_stage_team"),
    )

    workflow_stage_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow_stages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    execution_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    stage: Mapped["WorkflowStage"] = relationship("WorkflowStage", back_populates="team_assignments")
    team: Mapped["Team"] = relationship("Team", lazy="selectin")  # noqa: F821


class WorkflowRule(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workflow_rules"

    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_type: Mapped[WorkflowRuleType] = mapped_column(SAEnum(WorkflowRuleType), nullable=False)
    configuration_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="rules")
