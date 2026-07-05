"""Pydantic schemas for the enterprise SSO API.

Connection responses never include the OIDC client secret (only a
``has_client_secret`` flag); secrets are write-only on create/update.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.sso import SSOProtocol, SSOProvider


class SSOConnectionBase(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
    protocol: SSOProtocol
    provider: SSOProvider
    organization_id: str | None = None
    enabled: bool = True
    auto_provision: bool = True
    default_role: str = "VIEWER"
    allowed_email_domains: list[str] | None = None
    role_mappings: dict[str, str] | None = None
    organization_mappings: dict[str, str] | None = None

    subject_claim: str = "sub"
    email_claim: str = "email"
    name_claim: str = "name"
    groups_claim: str = "groups"

    # OIDC / OAuth2
    issuer: str | None = None
    client_id: str | None = None
    discovery_url: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    jwks_uri: str | None = None
    userinfo_endpoint: str | None = None
    scopes: list[str] | None = None
    use_pkce: bool = True

    # SAML 2.0
    idp_entity_id: str | None = None
    idp_sso_url: str | None = None
    idp_x509_cert: str | None = None
    idp_x509_cert_next: str | None = None
    sp_entity_id: str | None = None
    want_assertions_signed: bool = True
    allow_idp_initiated: bool = True

    # Single-logout endpoint (OIDC end_session_endpoint or SAML SLO URL).
    logout_url: str | None = None


class SSOConnectionCreate(SSOConnectionBase):
    slug: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    # Write-only OIDC client secret (stored encrypted, never returned).
    client_secret: str | None = None


class SSOConnectionUpdate(BaseModel):
    display_name: str | None = None
    enabled: bool | None = None
    auto_provision: bool | None = None
    default_role: str | None = None
    allowed_email_domains: list[str] | None = None
    role_mappings: dict[str, str] | None = None
    organization_mappings: dict[str, str] | None = None
    subject_claim: str | None = None
    email_claim: str | None = None
    name_claim: str | None = None
    groups_claim: str | None = None
    issuer: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    discovery_url: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    jwks_uri: str | None = None
    userinfo_endpoint: str | None = None
    scopes: list[str] | None = None
    use_pkce: bool | None = None
    idp_entity_id: str | None = None
    idp_sso_url: str | None = None
    idp_x509_cert: str | None = None
    idp_x509_cert_next: str | None = None
    sp_entity_id: str | None = None
    want_assertions_signed: bool | None = None
    allow_idp_initiated: bool | None = None
    logout_url: str | None = None


class SamlMetadataImportRequest(BaseModel):
    """Import IdP SAML metadata (paste XML or provide a URL)."""

    metadata_xml: str | None = None
    metadata_url: str | None = None


class SSOConnectionResponse(BaseModel):
    id: str
    slug: str
    display_name: str
    protocol: str
    provider: str
    organization_id: str | None
    enabled: bool
    auto_provision: bool
    default_role: str
    allowed_email_domains: list[str] | None
    role_mappings: dict[str, str] | None
    organization_mappings: dict[str, str] | None
    subject_claim: str
    email_claim: str
    name_claim: str
    groups_claim: str
    issuer: str | None
    client_id: str | None
    discovery_url: str | None
    authorization_endpoint: str | None
    token_endpoint: str | None
    jwks_uri: str | None
    userinfo_endpoint: str | None
    scopes: list[str] | None
    use_pkce: bool
    idp_entity_id: str | None
    idp_sso_url: str | None
    sp_entity_id: str | None
    want_assertions_signed: bool
    allow_idp_initiated: bool = True
    logout_url: str | None = None
    has_client_secret: bool = False
    has_idp_certificate: bool = False
    has_idp_certificate_next: bool = False

    model_config = {"from_attributes": True}


class SSOConnectionListResponse(BaseModel):
    connections: list[SSOConnectionResponse]
    total: int


class SSOProviderInfo(BaseModel):
    """Public, login-page-safe description of an enabled SSO connection."""

    slug: str
    display_name: str
    protocol: str
    provider: str
    login_url: str


class SSOProviderListResponse(BaseModel):
    providers: list[SSOProviderInfo]
