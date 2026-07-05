"""SCIM 2.0 provisioning models (RFC 7643/7644).

SCIM is organization-scoped: a ``ScimToken`` authenticates an IdP to exactly one
organization, and ``ScimUser`` / ``ScimGroup`` are the org-scoped SCIM resources
the IdP manages. ``ScimUser`` links to a global ``users`` row (and an
``organization_members`` row for the org role); ``ScimGroup`` membership drives
the member's organization role via the org's SSO role mappings.

Token material is stored only as a SHA-256 hash; the plaintext is shown once at
creation and never persisted.
"""

from __future__ import annotations

import enum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class ScimResourceType(str, enum.Enum):
    USER = "User"
    GROUP = "Group"


class ScimToken(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "scim_tokens"

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # SHA-256 hex of the bearer token (never the plaintext).
    hashed_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    # Non-secret display prefix, e.g. "scim_ab12…".
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ScimUser(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "scim_users"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_name", name="uq_scim_user_name"),
        UniqueConstraint("organization_id", "external_id", name="uq_scim_user_extid"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    given_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    family_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Full SCIM resource attributes as last received (audit / round-trip).
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ScimGroup(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "scim_groups"
    __table_args__ = (
        UniqueConstraint("organization_id", "display_name", name="uq_scim_group_name"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    # OrganizationRole this group grants members (resolved from SSO role mappings).
    mapped_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ScimGroupMember(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "scim_group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "scim_user_id", name="uq_scim_group_member"),
    )

    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scim_groups.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    scim_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scim_users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
