"""Sprint 51D - Interactive Product Tour.

Guided, in-app walkthroughs that help customers learn the platform without
reading docs. A ``ProductTour`` is a template (first-login onboarding or a
role-specific / module walkthrough) made of ordered ``ProductTourStep`` rows.
``ProductTourProgress`` tracks each user's position so they can resume later and
records completion.

Org-isolated and per-user. Default tours are idempotently seeded per
organization. No secrets stored. Strictly additive.
"""

import enum

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class TourAudience(str, enum.Enum):
    ALL = "ALL"
    EXECUTIVE = "EXECUTIVE"
    SRE = "SRE"
    DEVOPS_ENGINEER = "DEVOPS_ENGINEER"
    DEVELOPER = "DEVELOPER"
    ADMINISTRATOR = "ADMINISTRATOR"


class TourProgressStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class ProductTour(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "product_tours"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    audience: Mapped[str] = mapped_column(
        String(40), nullable=False, default=TourAudience.ALL.value, index=True
    )
    is_first_login: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ProductTourStep(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "product_tour_steps"

    tour_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("product_tours.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # UI anchoring + contextual help.
    target_route: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_selector: Mapped[str | None] = mapped_column(String(255), nullable=True)
    module: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    cta_label: Mapped[str | None] = mapped_column(String(120), nullable=True)


class ProductTourProgress(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "product_tour_progress"

    tour_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("product_tours.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TourProgressStatus.IN_PROGRESS.value, index=True
    )
    current_step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_step_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_activity_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
