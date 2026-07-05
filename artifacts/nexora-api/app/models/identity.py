"""Enterprise identity & access models (Sprint 61A).

Net-new identity primitives that complement the existing SSO / SCIM / audit
stack:

* ``ServiceAccount`` — a non-human organization principal with a role and
  scoped permissions.
* ``ApiKey`` — a hashed, prefix-addressable credential for an organization, a
  user (personal) or a service account. Secrets are stored only as SHA-256
  hashes; the plaintext is shown once at creation.
* ``UserSession`` — a database-backed session record (device history, refresh
  token rotation, revocation, concurrent-session limits).
* ``OrganizationSecurityPolicy`` — per-organization configurable security
  controls (password policy, MFA requirement, session timeout, allowed email
  domains, IP allow list, API-key policy).
* ``UserMfaTotp`` / ``MfaRecoveryCode`` — TOTP enrollment + single-use recovery
  codes.

Every mutation in the accompanying services emits a tamper-evident,
organization-scoped audit event via ``AuditLogRepository``.
"""

from __future__ import annotations

import enum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class ApiKeyPrincipalType(str, enum.Enum):
    """What kind of principal an API key authenticates as."""

    ORGANIZATION = "ORGANIZATION"  # acts for the whole org (machine-to-machine)
    USER = "USER"  # personal access token, acts as the owning user
    SERVICE_ACCOUNT = "SERVICE_ACCOUNT"  # acts as a service account


class ServiceAccount(Base, UUIDMixin, TimestampMixin):
    """A non-human principal owned by an organization."""

    __tablename__ = "service_accounts"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_service_account_name"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Org role granted to anything authenticating as this service account.
    role: Mapped[str] = mapped_column(String(20), default="VIEWER", nullable=False)
    # Fine-grained scopes (subset/refinement of the role). ``["*"]`` = all.
    scopes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ApiKey(Base, UUIDMixin, TimestampMixin):
    """A hashed API key. Looked up by non-secret ``prefix``; verified by hash."""

    __tablename__ = "api_keys"

    principal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Exactly one of the following identifies the principal (matched to type).
    organization_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    service_account_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("service_accounts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Non-secret, indexed lookup key (e.g. ``nxk_AbC12345``). Globally unique.
    prefix: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    # SHA-256 hex of the full secret; the plaintext is never persisted.
    hashed_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    scopes: Mapped[list | None] = mapped_column(JSON, nullable=True)

    expires_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    revoked_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class UserSession(Base, UUIDMixin, TimestampMixin):
    """Database-backed login session with refresh-token rotation support."""

    __tablename__ = "user_sessions"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # SHA-256 of the session's current refresh token (rotated on each refresh).
    refresh_token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    # jti of the access token most recently issued for this session.
    access_jti: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    device_label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    rotation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_seen_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    revoked_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)


class OrganizationSecurityPolicy(Base, UUIDMixin, TimestampMixin):
    """Per-organization configurable security controls (one row per org)."""

    __tablename__ = "organization_security_policies"

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Password policy
    password_min_length: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    password_require_uppercase: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    password_require_lowercase: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    password_require_number: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    password_require_symbol: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # MFA
    mfa_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Sessions
    session_timeout_minutes: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # 0 = use JWT default
    max_concurrent_sessions: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # 0 = unlimited

    # Access controls
    allowed_email_domains: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ip_allowlist: Mapped[list | None] = mapped_column(JSON, nullable=True)  # CIDRs

    # API-key policy
    api_keys_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    api_key_max_age_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    updated_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class UserMfaTotp(Base, UUIDMixin, TimestampMixin):
    """A user's TOTP authenticator enrollment (one active row per user)."""

    __tablename__ = "user_mfa_totp"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # AES-256-GCM encrypted base32 TOTP secret (via app.security.secrets).
    encrypted_secret: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmed_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class MfaRecoveryCode(Base, UUIDMixin, TimestampMixin):
    """Single-use MFA recovery (backup) code, stored hashed."""

    __tablename__ = "mfa_recovery_codes"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    used_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
