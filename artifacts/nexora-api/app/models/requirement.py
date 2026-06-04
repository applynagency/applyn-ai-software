from sqlalchemy import String, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from app.database.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin


class RequirementStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Requirement(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "requirements"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RequirementStatus] = mapped_column(
        SAEnum(RequirementStatus), default=RequirementStatus.PENDING, nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submitted_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False, index=True
    )

    project: Mapped["Project"] = relationship("Project", back_populates="requirements")  # noqa: F821
    agent_runs: Mapped[list["AgentRun"]] = relationship(  # noqa: F821
        "AgentRun", back_populates="requirement", lazy="selectin"
    )
