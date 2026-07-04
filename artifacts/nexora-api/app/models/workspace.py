"""Organization workspace model (projects container)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class Workspace(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True,
    )

    owner: Mapped["User"] = relationship("User", back_populates="workspaces")  # noqa: F821
    organization: Mapped["Organization | None"] = relationship(  # noqa: F821
        "Organization", back_populates="workspaces",
    )
    projects: Mapped[list["Project"]] = relationship(  # noqa: F821
        "Project", back_populates="workspace", lazy="selectin",
    )
