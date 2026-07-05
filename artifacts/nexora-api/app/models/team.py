import enum

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDMixin


class TeamType(str, enum.Enum):
    PRODUCT = "PRODUCT"
    UI_UX = "UI_UX"
    FRONTEND = "FRONTEND"
    BACKEND = "BACKEND"
    QA = "QA"
    DEVOPS = "DEVOPS"
    DEPLOYMENT = "DEPLOYMENT"
    SECURITY = "SECURITY"
    COMPLIANCE = "COMPLIANCE"
    CUSTOM = "CUSTOM"


class TeamStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class ResponsibilityPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Team(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "teams"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    team_type: Mapped[TeamType] = mapped_column(SAEnum(TeamType), nullable=False)
    status: Mapped[TeamStatus] = mapped_column(
        SAEnum(TeamStatus), default=TeamStatus.ACTIVE, nullable=False
    )
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )

    organization: Mapped["Organization"] = relationship("Organization")  # noqa: F821
    responsibilities: Mapped[list["TeamResponsibility"]] = relationship(
        "TeamResponsibility",
        back_populates="team",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    agent_mappings: Mapped[list["TeamAgentMapping"]] = relationship(
        "TeamAgentMapping",
        back_populates="team",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class TeamResponsibility(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "team_responsibilities"

    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[ResponsibilityPriority] = mapped_column(
        SAEnum(ResponsibilityPriority), default=ResponsibilityPriority.MEDIUM, nullable=False
    )

    team: Mapped["Team"] = relationship("Team", back_populates="responsibilities")


class TeamAgentMapping(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "team_agent_mappings"

    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    internal_agent: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    execution_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    team: Mapped["Team"] = relationship("Team", back_populates="agent_mappings")
