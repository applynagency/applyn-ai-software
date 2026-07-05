"""Enterprise SSO models.

``SSOConnection`` stores a configured identity-provider connection (OIDC or
SAML) for Microsoft Entra, Okta, Google Workspace, Ping or any generic provider.
A connection may be scoped to a single organization or be tenant-wide (with
organization mapping driven by IdP claims). ``SSOIdentity`` links an external
IdP subject (OIDC ``sub`` / SAML ``NameID``) to a local user so repeat logins
resolve to the same account.

Secrets (OIDC client secret) are stored AES-256-GCM encrypted via
``app.security.secrets.get_cipher`` and never returned in API responses.
"""

from __future__ import annotations

import enum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base, TimestampMixin, UUIDMixin


class SSOProtocol(str, enum.Enum):
    OIDC = "OIDC"
    SAML = "SAML"


class SSOProvider(str, enum.Enum):
    ENTRA = "ENTRA"  # Microsoft Entra ID (Azure AD)
    OKTA = "OKTA"
    GOOGLE = "GOOGLE"  # Google Workspace
    PING = "PING"  # PingFederate / PingOne / Ping Identity
    AUTH0 = "AUTH0"  # Auth0 (Okta CIC)
    KEYCLOAK = "KEYCLOAK"  # Keycloak / Red Hat SSO
    ONELOGIN = "ONELOGIN"  # OneLogin (SAML)
    GENERIC_OIDC = "GENERIC_OIDC"
    GENERIC_SAML = "GENERIC_SAML"


class SSOConnection(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sso_connections"

    # Tenant-wide when organization_id is NULL; otherwise scoped to one org.
    organization_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    # URL-safe identifier used in /auth/sso/<slug>/... routes.
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    protocol: Mapped[str] = mapped_column(String(10), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Provisioning / mapping policy.
    auto_provision: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_role: Mapped[str] = mapped_column(String(20), default="VIEWER", nullable=False)
    # Restrict logins to these email domains (empty = any).
    allowed_email_domains: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # {idp_group_or_role: OrganizationRole} — highest-privilege match wins.
    role_mappings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # {idp_group_or_email_domain: organization_slug} for tenant-wide connections.
    organization_mappings: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Claim/attribute names used to extract identity from the IdP response.
    subject_claim: Mapped[str] = mapped_column(String(64), default="sub", nullable=False)
    email_claim: Mapped[str] = mapped_column(String(64), default="email", nullable=False)
    name_claim: Mapped[str] = mapped_column(String(64), default="name", nullable=False)
    groups_claim: Mapped[str] = mapped_column(String(64), default="groups", nullable=False)

    # --- OIDC / OAuth2 ---
    issuer: Mapped[str | None] = mapped_column(String(512), nullable=True)
    client_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    encrypted_client_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovery_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    authorization_endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    token_endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    jwks_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    userinfo_endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    scopes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    use_pkce: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Single-logout endpoint (OIDC end_session_endpoint or SAML SLO URL).
    logout_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # --- SAML 2.0 ---
    idp_entity_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    idp_sso_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    idp_x509_cert: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Secondary cert to support zero-downtime certificate rotation: assertions
    # signed by either the primary or the next cert verify during a rollover.
    idp_x509_cert_next: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Raw IdP metadata XML retained from the most recent metadata import.
    idp_metadata_xml: Mapped[str | None] = mapped_column(Text, nullable=True)
    sp_entity_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    want_assertions_signed: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    # Accept unsolicited (IdP-initiated) SAML responses at the ACS endpoint.
    allow_idp_initiated: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class SSOIdentity(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sso_identities"
    __table_args__ = (
        UniqueConstraint("connection_id", "external_subject", name="uq_sso_identity"),
    )

    connection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sso_connections.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    last_login_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
