"""Sprint 51A - Product Documentation Center.

A centralized, org-scoped documentation system. ``DocumentationCategory`` groups
articles into a navigable tree (Getting Started, Onboarding, Monitoring, ...).
``DocumentationArticle`` stores markdown content with first-class support for
screenshots, code snippets and embedded videos, plus inline version history
(``revisions``), view tracking and a last-updated timestamp.

Everything is org-isolated. Default categories are idempotently seeded per
organization. Nothing here executes actions or stores secrets.
"""

import enum

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class DocArticleStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class DocumentationCategory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "documentation_categories"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(40), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("documentation_categories.id", ondelete="CASCADE"), nullable=True, index=True
    )
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DocumentationArticle(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "documentation_articles"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documentation_categories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Primary body, authored in Markdown.
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DocArticleStatus.PUBLISHED.value, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Structured rich media (also embeddable inline in Markdown).
    screenshots: Mapped[list | None] = mapped_column(JSON, nullable=True)      # [{url, caption}]
    code_snippets: Mapped[list | None] = mapped_column(JSON, nullable=True)    # [{language, code, caption}]
    videos: Mapped[list | None] = mapped_column(JSON, nullable=True)          # [{url, title, provider}]
    # Inline version history (snapshots of prior versions); keeps to 2 tables.
    revisions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
