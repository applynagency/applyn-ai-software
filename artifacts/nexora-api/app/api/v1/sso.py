"""Enterprise SSO API.

Public:
* ``GET  /auth/sso/providers``                 — enabled providers (login page)
* ``GET  /auth/sso/{slug}/login``              — start login (redirect to IdP)
* ``GET  /auth/sso/{slug}/callback``           — OIDC authorization-code callback
* ``POST /auth/sso/{slug}/acs``                — SAML assertion consumer service
* ``GET  /auth/sso/{slug}/metadata``           — SAML SP metadata (XML)

Admin (superuser):
* ``POST/GET/PATCH/DELETE /auth/sso/connections[/{id}]`` — manage IdP connections
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContext, OrgContextDep
from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.organization import OrganizationRole
from app.models.sso import SSOProtocol
from app.models.user import User
from app.repositories.sso import SSOConnectionRepository
from app.schemas.auth import TokenResponse
from app.schemas.sso import (
    SamlMetadataImportRequest,
    SSOConnectionCreate,
    SSOConnectionListResponse,
    SSOConnectionResponse,
    SSOConnectionUpdate,
    SSOProviderInfo,
    SSOProviderListResponse,
)
from app.security.secrets import get_cipher
from app.services.sso import presets
from app.services.sso.oidc import OIDCService, generate_pkce
from app.services.sso.provisioning import SSOProvisioningService
from app.services.sso.saml import SAMLService, parse_idp_metadata
from app.services.sso.state import consume_state, create_state, new_nonce

router = APIRouter(prefix="/auth/sso", tags=["SSO"])


@dataclass
class SsoAdminContext:
    user: User
    organization_id: str | None
    is_superuser: bool


async def require_sso_admin(
    current_user: CurrentUser, org: OrgContextDep
) -> SsoAdminContext:
    if current_user.is_superuser:
        return SsoAdminContext(
            user=current_user,
            organization_id=org.organization_id,
            is_superuser=True,
        )
    org_id = org.requires_organization
    if org.role not in (OrganizationRole.OWNER, OrganizationRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SSO configuration requires organization OWNER or ADMIN",
        )
    return SsoAdminContext(
        user=current_user, organization_id=org_id, is_superuser=False
    )


SsoAdmin = Annotated[SsoAdminContext, Depends(require_sso_admin)]


def _ensure_connection_access(admin: SsoAdminContext, conn) -> None:
    if admin.is_superuser:
        return
    if conn.organization_id != admin.organization_id:
        raise NotFoundError("SSO connection not found")


# --- helpers ----------------------------------------------------------------


def _ensure_enabled() -> None:
    if not settings.SSO_ENABLED:
        raise NotFoundError("SSO is not enabled")


def _public_url_for(request: Request, name: str, slug: str) -> str:
    """Absolute URL for a named route, honoring SSO_PUBLIC_BASE_URL behind proxies."""
    url = str(request.url_for(name, slug=slug))
    if settings.SSO_PUBLIC_BASE_URL:
        parsed = urlsplit(url)
        return settings.SSO_PUBLIC_BASE_URL.rstrip("/") + parsed.path
    return url


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def _to_response(conn) -> SSOConnectionResponse:
    return SSOConnectionResponse(
        id=conn.id,
        slug=conn.slug,
        display_name=conn.display_name,
        protocol=conn.protocol,
        provider=conn.provider,
        organization_id=conn.organization_id,
        enabled=conn.enabled,
        auto_provision=conn.auto_provision,
        default_role=conn.default_role,
        allowed_email_domains=conn.allowed_email_domains,
        role_mappings=conn.role_mappings,
        organization_mappings=conn.organization_mappings,
        subject_claim=conn.subject_claim,
        email_claim=conn.email_claim,
        name_claim=conn.name_claim,
        groups_claim=conn.groups_claim,
        issuer=conn.issuer,
        client_id=conn.client_id,
        discovery_url=conn.discovery_url,
        authorization_endpoint=conn.authorization_endpoint,
        token_endpoint=conn.token_endpoint,
        jwks_uri=conn.jwks_uri,
        userinfo_endpoint=conn.userinfo_endpoint,
        scopes=conn.scopes,
        use_pkce=conn.use_pkce,
        idp_entity_id=conn.idp_entity_id,
        idp_sso_url=conn.idp_sso_url,
        sp_entity_id=conn.sp_entity_id,
        want_assertions_signed=conn.want_assertions_signed,
        allow_idp_initiated=conn.allow_idp_initiated,
        logout_url=conn.logout_url,
        has_client_secret=bool(conn.encrypted_client_secret),
        has_idp_certificate=bool(conn.idp_x509_cert),
        has_idp_certificate_next=bool(conn.idp_x509_cert_next),
    )


async def _load_connection(session, slug: str, *, require_enabled: bool = False):
    repo = SSOConnectionRepository(session)
    conn = await repo.get_by_slug(slug)
    if conn is None or (require_enabled and not conn.enabled):
        raise NotFoundError(f"SSO provider '{slug}' not found")
    return conn


# --- public: provider discovery + login flows -------------------------------


@router.get("/providers", response_model=SSOProviderListResponse)
async def list_providers(request: Request, session: DBSession):
    _ensure_enabled()
    repo = SSOConnectionRepository(session)
    providers = [
        SSOProviderInfo(
            slug=c.slug,
            display_name=c.display_name,
            protocol=c.protocol,
            provider=c.provider,
            login_url=_public_url_for(request, "sso_login", c.slug),
        )
        for c in await repo.list_enabled()
    ]
    return SSOProviderListResponse(providers=providers)


@router.get("/{slug}/login", name="sso_login")
async def login(slug: str, request: Request, session: DBSession):
    _ensure_enabled()
    conn = await _load_connection(session, slug, require_enabled=True)

    if conn.protocol == SSOProtocol.OIDC.value:
        oidc = OIDCService(conn)
        code_verifier = code_challenge = None
        if conn.use_pkce:
            code_verifier, code_challenge = generate_pkce()
        nonce = new_nonce()
        state = await create_state(conn.id, nonce, code_verifier)
        redirect_uri = _public_url_for(request, "sso_oidc_callback", slug)
        url = await oidc.authorization_url(
            redirect_uri=redirect_uri,
            state=state,
            nonce=nonce,
            code_challenge=code_challenge,
        )
        return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    saml = SAMLService(conn)
    acs_url = _public_url_for(request, "sso_saml_acs", slug)
    url = saml.build_authn_request_redirect(acs_url=acs_url)
    return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/{slug}/callback", name="sso_oidc_callback", response_model=TokenResponse)
async def oidc_callback(
    slug: str,
    request: Request,
    session: DBSession,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    _ensure_enabled()
    if error:
        raise ValidationError(f"Identity provider returned an error: {error_description or error}")
    if not code or not state:
        raise ValidationError("Missing authorization code or state")

    record = await consume_state(state)
    if not record:
        raise ValidationError("Invalid or expired SSO state")

    conn = await _load_connection(session, slug, require_enabled=True)
    if record.get("connection_id") != conn.id:
        raise ValidationError("SSO state does not match this provider")

    redirect_uri = _public_url_for(request, "sso_oidc_callback", slug)
    oidc = OIDCService(conn)
    claims = await oidc.fetch_claims(
        code=code,
        redirect_uri=redirect_uri,
        expected_nonce=record.get("nonce"),
        code_verifier=record.get("code_verifier"),
    )
    service = SSOProvisioningService(session)
    return await service.provision_and_issue(
        conn,
        claims,
        ip=_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )


@router.post("/{slug}/acs", name="sso_saml_acs", response_model=TokenResponse)
async def saml_acs(
    slug: str,
    request: Request,
    session: DBSession,
    SAMLResponse: str = Form(...),
    RelayState: str | None = Form(None),
):
    _ensure_enabled()
    conn = await _load_connection(session, slug, require_enabled=True)
    if conn.protocol != SSOProtocol.SAML.value:
        raise ValidationError("This connection does not use SAML")

    acs_url = _public_url_for(request, "sso_saml_acs", slug)
    saml = SAMLService(conn)
    claims = saml.parse_and_validate_response(SAMLResponse, acs_url=acs_url)
    service = SSOProvisioningService(session)
    return await service.provision_and_issue(
        conn,
        claims,
        ip=_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )


@router.get("/{slug}/metadata", name="sso_saml_metadata")
async def saml_metadata(slug: str, request: Request, session: DBSession):
    _ensure_enabled()
    conn = await _load_connection(session, slug)
    if conn.protocol != SSOProtocol.SAML.value:
        raise NotFoundError(f"SSO provider '{slug}' does not expose SAML metadata")
    acs_url = _public_url_for(request, "sso_saml_acs", slug)
    sp_entity_id = conn.sp_entity_id or _public_url_for(request, "sso_saml_metadata", slug)
    saml = SAMLService(conn)
    xml = saml.sp_metadata(sp_entity_id=sp_entity_id, acs_url=acs_url)
    return Response(content=xml, media_type="application/samlmetadata+xml")


# --- admin: SAML metadata import --------------------------------------------


@router.post(
    "/connections/{connection_id}/saml/import-metadata",
    response_model=SSOConnectionResponse,
)
async def import_saml_metadata(
    connection_id: str,
    payload: SamlMetadataImportRequest,
    admin: SsoAdmin,
    session: DBSession,
):
    """Populate a SAML connection from an IdP metadata document (XML or URL)."""
    repo = SSOConnectionRepository(session)
    conn = await repo.get_by_id(connection_id)
    if conn is None:
        raise NotFoundError("SSO connection not found")
    _ensure_connection_access(admin, conn)
    if conn.protocol != SSOProtocol.SAML.value:
        raise ValidationError("Metadata import only applies to SAML connections")

    metadata_xml = payload.metadata_xml
    if not metadata_xml and payload.metadata_url:
        from app.security.ssrf import safe_http_client

        async with safe_http_client(timeout=10.0) as client:
            resp = await client.get(payload.metadata_url)
            resp.raise_for_status()
            metadata_xml = resp.text
    if not metadata_xml:
        raise ValidationError("Provide metadata_xml or metadata_url")

    parsed = parse_idp_metadata(metadata_xml)
    updates = {k: v for k, v in parsed.items() if v}
    updates["idp_metadata_xml"] = metadata_xml
    await repo.update(conn, **updates)
    return _to_response(conn)


# --- admin: connection management -------------------------------------------


@router.post(
    "/connections",
    response_model=SSOConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_connection(
    payload: SSOConnectionCreate, admin: SsoAdmin, session: DBSession
):
    repo = SSOConnectionRepository(session)
    if await repo.get_by_slug(payload.slug):
        raise ConflictError(f"SSO connection '{payload.slug}' already exists")

    provider = payload.provider.value
    protocol = payload.protocol.value
    scopes = payload.scopes
    issuer = payload.issuer
    if protocol == SSOProtocol.OIDC.value:
        if scopes is None:
            scopes = presets.default_scopes(provider)
        if issuer is None:
            issuer = presets.PROVIDER_DEFAULTS.get(provider, {}).get("issuer")

    encrypted_secret = (
        get_cipher().encrypt(payload.client_secret) if payload.client_secret else None
    )
    org_id = admin.organization_id if not admin.is_superuser else payload.organization_id

    conn = await repo.create(
        slug=payload.slug,
        display_name=payload.display_name,
        protocol=protocol,
        provider=provider,
        organization_id=org_id,
        enabled=payload.enabled,
        auto_provision=payload.auto_provision,
        default_role=payload.default_role,
        allowed_email_domains=payload.allowed_email_domains,
        role_mappings=payload.role_mappings,
        organization_mappings=payload.organization_mappings,
        subject_claim=payload.subject_claim,
        email_claim=payload.email_claim,
        name_claim=payload.name_claim,
        groups_claim=payload.groups_claim,
        issuer=issuer,
        client_id=payload.client_id,
        encrypted_client_secret=encrypted_secret,
        discovery_url=payload.discovery_url,
        authorization_endpoint=payload.authorization_endpoint,
        token_endpoint=payload.token_endpoint,
        jwks_uri=payload.jwks_uri,
        userinfo_endpoint=payload.userinfo_endpoint,
        scopes=scopes,
        use_pkce=payload.use_pkce,
        idp_entity_id=payload.idp_entity_id,
        idp_sso_url=payload.idp_sso_url,
        idp_x509_cert=payload.idp_x509_cert,
        idp_x509_cert_next=payload.idp_x509_cert_next,
        sp_entity_id=payload.sp_entity_id,
        want_assertions_signed=payload.want_assertions_signed,
        allow_idp_initiated=payload.allow_idp_initiated,
        logout_url=payload.logout_url,
        created_by=admin.user.id,
    )
    return _to_response(conn)


@router.get("/connections", response_model=SSOConnectionListResponse)
async def list_connections(admin: SsoAdmin, session: DBSession):
    repo = SSOConnectionRepository(session)
    org_filter = None if admin.is_superuser else admin.organization_id
    conns = await repo.list_for_organization(org_filter)
    return SSOConnectionListResponse(
        connections=[_to_response(c) for c in conns], total=len(conns)
    )


@router.get("/connections/{connection_id}", response_model=SSOConnectionResponse)
async def get_connection(
    connection_id: str, admin: SsoAdmin, session: DBSession
):
    repo = SSOConnectionRepository(session)
    conn = await repo.get_by_id(connection_id)
    if conn is None:
        raise NotFoundError("SSO connection not found")
    _ensure_connection_access(admin, conn)
    return _to_response(conn)


@router.patch("/connections/{connection_id}", response_model=SSOConnectionResponse)
async def update_connection(
    connection_id: str,
    payload: SSOConnectionUpdate,
    admin: SsoAdmin,
    session: DBSession,
):
    repo = SSOConnectionRepository(session)
    conn = await repo.get_by_id(connection_id)
    if conn is None:
        raise NotFoundError("SSO connection not found")
    _ensure_connection_access(admin, conn)

    changes = payload.model_dump(exclude_unset=True)
    if "client_secret" in changes:
        secret = changes.pop("client_secret")
        conn.encrypted_client_secret = (
            get_cipher().encrypt(secret) if secret else None
        )
    if changes:
        await repo.update(conn, **changes)
    else:
        await session.flush()
    return _to_response(conn)


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: str, admin: SsoAdmin, session: DBSession
):
    repo = SSOConnectionRepository(session)
    conn = await repo.get_by_id(connection_id)
    if conn is None:
        raise NotFoundError("SSO connection not found")
    _ensure_connection_access(admin, conn)
    await repo.hard_delete(conn)
