"""Sprint 51C - Screenshot & Demo Asset Manager.

A ``DemoAsset`` is an org-scoped reference to a screenshot, image or demo video
for a platform feature. Assets are stored by URL reference (object storage /
CDN); this model holds the metadata used to build a demo gallery: category,
module mapping, description, tags and media attributes.

Org-isolated. No secrets stored. Strictly additive.
"""

import enum

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class DemoAssetCategory(str, enum.Enum):
    DASHBOARD = "DASHBOARD"
    DISCOVERY = "DISCOVERY"
    MONITORING = "MONITORING"
    INCIDENTS = "INCIDENTS"
    TIMELINE = "TIMELINE"
    CHANGE_INTELLIGENCE = "CHANGE_INTELLIGENCE"
    RECOMMENDATIONS = "RECOMMENDATIONS"
    REMEDIATION = "REMEDIATION"
    SLO = "SLO"
    CAPACITY = "CAPACITY"
    COST = "COST"
    REPORTS = "REPORTS"
    AI_COPILOT = "AI_COPILOT"
    WAR_ROOM = "WAR_ROOM"


class DemoAssetType(str, enum.Enum):
    SCREENSHOT = "SCREENSHOT"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"


class DemoAsset(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "demo_assets"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(
        String(40), nullable=False, default=DemoAssetCategory.DASHBOARD.value, index=True
    )
    asset_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DemoAssetType.SCREENSHOT.value, index=True
    )
    # Module mapping (e.g. "monitoring", "ai-copilot") for feature-to-asset tracking.
    module: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
