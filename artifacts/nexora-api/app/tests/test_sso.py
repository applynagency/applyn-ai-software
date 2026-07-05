"""Enterprise SSO tests — OIDC + SAML, provisioning, role/org mapping, admin CRUD.

OIDC ID tokens are signed locally with a throwaway RSA key (verified against a
JWKS built from its public key), and SAML responses are signed end-to-end with
signxml, so the real verification paths run without any live IdP.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from jose import jwk
from jose import jwt as jose_jwt

from app.core.security import decode_token
from app.database.session import AsyncSessionLocal
from app.models.organization import OrganizationRole
from app.models.sso import SSOConnection
from app.repositories.user import UserRepository
from app.services.sso.oidc import OIDCService
from app.services.sso.provisioning import SSOProvisioningService
from app.services.sso.state import create_state

from .conftest import auth_headers, create_authenticated_user, create_organization

pytestmark = pytest.mark.asyncio


# --- shared crypto material -------------------------------------------------

_RSA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PRIVATE_PEM = _RSA.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
_PUBLIC_PEM = (
    _RSA.public_key()
    .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    .decode()
)


def _jwks(kid: str = "test-kid") -> dict:
    raw = jwk.construct(_PUBLIC_PEM, "RS256").to_dict()
    out = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in raw.items()}
    out["kid"] = kid
    out["use"] = "sig"
    out["alg"] = "RS256"
    return {"keys": [out]}


def _id_token(*, issuer, audience, sub, email, name=None, groups=None, nonce=None) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": issuer,
        "aud": audience,
        "sub": sub,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    if name:
        claims["name"] = name
    if groups is not None:
        claims["groups"] = groups
    if nonce is not None:
        claims["nonce"] = nonce
    return jose_jwt.encode(claims, _PRIVATE_PEM, algorithm="RS256", headers={"kid": "test-kid"})


_SAML_CERT = (
    x509.CertificateBuilder()
    .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "idp.example.com")]))
    .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "idp.example.com")]))
    .public_key(_RSA.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.now(UTC) - timedelta(days=1))
    .not_valid_after(datetime.now(UTC) + timedelta(days=3650))
    .sign(_RSA, hashes.SHA256())
)
_CERT_PEM = _SAML_CERT.public_bytes(serialization.Encoding.PEM).decode()


def _build_signed_saml_response(
    *, issuer, sp_entity_id, acs_url, name_id, email, name=None, groups=None
) -> str:
    """Build a SAML Response whose Response element is XML-DSIG signed."""
    from lxml import etree
    from signxml import XMLSigner, methods

    saml = "urn:oasis:names:tc:SAML:2.0:assertion"
    samlp = "urn:oasis:names:tc:SAML:2.0:protocol"
    now = datetime.now(UTC)
    instant = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    not_after = (now + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    not_before = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

    nsmap = {"samlp": samlp, "saml": saml}
    resp = etree.Element(f"{{{samlp}}}Response", nsmap=nsmap)
    resp.set("ID", "_resp1")
    resp.set("Version", "2.0")
    resp.set("IssueInstant", instant)
    resp.set("Destination", acs_url)
    r_issuer = etree.SubElement(resp, f"{{{saml}}}Issuer")
    r_issuer.text = issuer
    status = etree.SubElement(resp, f"{{{samlp}}}Status")
    sc = etree.SubElement(status, f"{{{samlp}}}StatusCode")
    sc.set("Value", "urn:oasis:names:tc:SAML:2.0:status:Success")

    assertion = etree.SubElement(resp, f"{{{saml}}}Assertion")
    assertion.set("ID", "_assert1")
    assertion.set("Version", "2.0")
    assertion.set("IssueInstant", instant)
    a_issuer = etree.SubElement(assertion, f"{{{saml}}}Issuer")
    a_issuer.text = issuer

    subject = etree.SubElement(assertion, f"{{{saml}}}Subject")
    nid = etree.SubElement(subject, f"{{{saml}}}NameID")
    nid.set("Format", "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress")
    nid.text = name_id
    confirm = etree.SubElement(subject, f"{{{saml}}}SubjectConfirmation")
    confirm.set("Method", "urn:oasis:names:tc:SAML:2.0:cm:bearer")
    scd = etree.SubElement(confirm, f"{{{saml}}}SubjectConfirmationData")
    scd.set("NotOnOrAfter", not_after)
    scd.set("Recipient", acs_url)

    conditions = etree.SubElement(assertion, f"{{{saml}}}Conditions")
    conditions.set("NotBefore", not_before)
    conditions.set("NotOnOrAfter", not_after)
    ar = etree.SubElement(conditions, f"{{{saml}}}AudienceRestriction")
    aud = etree.SubElement(ar, f"{{{saml}}}Audience")
    aud.text = sp_entity_id

    stmt = etree.SubElement(assertion, f"{{{saml}}}AttributeStatement")

    def _attr(attr_name, values):
        attr = etree.SubElement(stmt, f"{{{saml}}}Attribute")
        attr.set("Name", attr_name)
        for v in values:
            av = etree.SubElement(attr, f"{{{saml}}}AttributeValue")
            av.text = v

    _attr("email", [email])
    if name:
        _attr("name", [name])
    if groups:
        _attr("groups", groups)

    signed = XMLSigner(
        method=methods.enveloped,
        signature_algorithm="rsa-sha256",
        digest_algorithm="sha256",
        c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#",
    ).sign(resp, key=_PRIVATE_PEM.encode(), cert=_CERT_PEM, reference_uri="_resp1")

    xml_bytes = etree.tostring(signed)
    return base64.b64encode(xml_bytes).decode()


# --- helpers ----------------------------------------------------------------


async def _make_superuser(email: str) -> None:
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_email(email)
        user.is_superuser = True
        session.add(user)
        await session.commit()


async def _superuser_token(client) -> str:
    _, tokens = await create_authenticated_user(
        client, email="ssoadmin@example.com", username="ssoadmin"
    )
    await _make_superuser("ssoadmin@example.com")
    return tokens["access_token"]


async def _create_oidc_connection(client, token, **overrides) -> dict:
    payload = {
        "slug": "acme-oidc",
        "display_name": "Acme OIDC",
        "protocol": "OIDC",
        "provider": "OKTA",
        "issuer": "https://idp.example.com",
        "client_id": "client-123",
        "client_secret": "topsecret",
        "authorization_endpoint": "https://idp.example.com/authorize",
        "token_endpoint": "https://idp.example.com/token",
        "jwks_uri": "https://idp.example.com/jwks",
        "role_mappings": {"admins": "ADMIN"},
    }
    payload.update(overrides)
    resp = await client.post(
        "/v1/auth/sso/connections", headers=auth_headers(token), json=payload
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- role mapping (unit) ----------------------------------------------------


async def test_role_mapping_picks_highest_privilege():
    conn = SSOConnection(
        role_mappings={"admins": "ADMIN", "devs": "DEVELOPER"}, default_role="VIEWER"
    )
    svc = SSOProvisioningService(session=None)
    assert svc.resolve_role(conn, ["devs", "admins"]) == OrganizationRole.ADMIN
    assert svc.resolve_role(conn, ["devs"]) == OrganizationRole.DEVELOPER


async def test_role_mapping_falls_back_to_default():
    conn = SSOConnection(role_mappings={"admins": "ADMIN"}, default_role="DEVELOPER")
    svc = SSOProvisioningService(session=None)
    assert svc.resolve_role(conn, ["unknown"]) == OrganizationRole.DEVELOPER
    assert svc.resolve_role(conn, []) == OrganizationRole.DEVELOPER


# --- admin CRUD -------------------------------------------------------------


async def test_admin_crud_hides_secret(client):
    token = await _superuser_token(client)
    created = await _create_oidc_connection(client, token)
    assert created["has_client_secret"] is True
    assert "client_secret" not in created
    assert "encrypted_client_secret" not in created

    conn_id = created["id"]
    got = await client.get(
        f"/v1/auth/sso/connections/{conn_id}", headers=auth_headers(token)
    )
    assert got.status_code == 200
    assert got.json()["client_id"] == "client-123"

    listed = await client.get("/v1/auth/sso/connections", headers=auth_headers(token))
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    patched = await client.patch(
        f"/v1/auth/sso/connections/{conn_id}",
        headers=auth_headers(token),
        json={"display_name": "Renamed", "enabled": False},
    )
    assert patched.status_code == 200
    assert patched.json()["display_name"] == "Renamed"
    assert patched.json()["enabled"] is False

    deleted = await client.delete(
        f"/v1/auth/sso/connections/{conn_id}", headers=auth_headers(token)
    )
    assert deleted.status_code == 204


async def test_member_cannot_manage_sso(client):
    _, tokens = await create_authenticated_user(
        client, email="viewer@example.com", username="vieweruser"
    )
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_email("viewer@example.com")
        from app.models.organization import OrganizationMember

        members = (
            await session.execute(
                select(OrganizationMember).where(OrganizationMember.user_id == user.id)
            )
        ).scalars().all()
        for member in members:
            member.role = OrganizationRole.VIEWER
            session.add(member)
        await session.commit()
    resp = await client.get(
        "/v1/auth/sso/connections", headers=auth_headers(tokens["access_token"])
    )
    assert resp.status_code == 403


async def test_org_owner_can_crud_own_org_connection(client):
    _, tokens = await create_authenticated_user(
        client, email="owner@example.com", username="orgowner"
    )
    org = await create_organization(
        client, tokens["access_token"], name="Owner Org", slug="owner-org"
    )
    token = org["context"]["access_token"]
    created = await _create_oidc_connection(
        client,
        token,
        slug="owner-oidc",
        organization_id=org["id"],
    )
    assert created["organization_id"] == org["id"]
    assert "client_secret" not in created

    listed = await client.get("/v1/auth/sso/connections", headers=auth_headers(token))
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    conn_id = created["id"]
    patched = await client.patch(
        f"/v1/auth/sso/connections/{conn_id}",
        headers=auth_headers(token),
        json={"enabled": False},
    )
    assert patched.status_code == 200
    assert patched.json()["enabled"] is False

    deleted = await client.delete(
        f"/v1/auth/sso/connections/{conn_id}", headers=auth_headers(token)
    )
    assert deleted.status_code == 204


async def test_org_admin_cannot_access_other_org_connection(client):
    _, tokens_a = await create_authenticated_user(
        client, email="ownera@example.com", username="ownera"
    )
    org_a = await create_organization(
        client, tokens_a["access_token"], name="Org A", slug="org-a-sso"
    )
    token_a = org_a["context"]["access_token"]

    su_token = await _superuser_token(client)
    conn_b = await _create_oidc_connection(
        client,
        su_token,
        slug="org-b-oidc",
        organization_id=None,
    )

    got = await client.get(
        f"/v1/auth/sso/connections/{conn_b['id']}",
        headers=auth_headers(token_a),
    )
    assert got.status_code == 404

    listed = await client.get("/v1/auth/sso/connections", headers=auth_headers(token_a))
    assert listed.status_code == 200
    assert listed.json()["total"] == 0


async def test_org_owner_create_forces_organization_scope(client):
    _, tokens = await create_authenticated_user(
        client, email="scoped@example.com", username="scopeduser"
    )
    token = tokens["access_token"]
    claims = decode_token(token)
    org_id = claims["organization_id"]
    resp = await client.post(
        "/v1/auth/sso/connections",
        headers=auth_headers(token),
        json={
            "slug": "scoped-oidc",
            "display_name": "Scoped",
            "protocol": "OIDC",
            "provider": "OKTA",
            "issuer": "https://idp.example.com",
            "client_id": "cid",
            "client_secret": "secret",
            "authorization_endpoint": "https://idp.example.com/authorize",
            "token_endpoint": "https://idp.example.com/token",
            "jwks_uri": "https://idp.example.com/jwks",
            "organization_id": None,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["organization_id"] == org_id


async def test_duplicate_slug_conflict(client):
    token = await _superuser_token(client)
    await _create_oidc_connection(client, token)
    dup = await client.post(
        "/v1/auth/sso/connections",
        headers=auth_headers(token),
        json={
            "slug": "acme-oidc",
            "display_name": "Dup",
            "protocol": "OIDC",
            "provider": "OKTA",
        },
    )
    assert dup.status_code == 409


# --- provider discovery + login redirect ------------------------------------


async def test_providers_list_is_public(client):
    token = await _superuser_token(client)
    await _create_oidc_connection(client, token)
    resp = await client.get("/v1/auth/sso/providers")
    assert resp.status_code == 200
    providers = resp.json()["providers"]
    assert len(providers) == 1
    assert providers[0]["slug"] == "acme-oidc"
    assert "/auth/sso/acme-oidc/login" in providers[0]["login_url"]


async def test_oidc_login_redirects_to_idp(client):
    token = await _superuser_token(client)
    await _create_oidc_connection(client, token)
    resp = await client.get("/v1/auth/sso/acme-oidc/login")
    assert resp.status_code == 307
    location = resp.headers["location"]
    assert location.startswith("https://idp.example.com/authorize")
    assert "client_id=client-123" in location
    assert "state=" in location
    assert "code_challenge=" in location
    assert "nonce=" in location


async def test_login_disabled_connection_404(client):
    token = await _superuser_token(client)
    await _create_oidc_connection(client, token, enabled=False)
    resp = await client.get("/v1/auth/sso/acme-oidc/login")
    assert resp.status_code == 404


# --- OIDC callback end to end -----------------------------------------------


async def test_oidc_callback_provisions_and_maps_role(client, monkeypatch):
    token = await _superuser_token(client)
    created = await _create_oidc_connection(client, token)
    conn_id = created["id"]

    nonce = "nonce-123"
    state = await create_state(conn_id, nonce, "verifier")
    id_token = _id_token(
        issuer="https://idp.example.com",
        audience="client-123",
        sub="okta|abc",
        email="alice@corp.com",
        name="Alice",
        groups=["admins"],
        nonce=nonce,
    )

    async def fake_exchange(self, *, code, redirect_uri, code_verifier=None):
        return {"id_token": id_token, "access_token": "opaque"}

    async def fake_jwks(self):
        return _jwks()

    monkeypatch.setattr(OIDCService, "exchange_code", fake_exchange)
    monkeypatch.setattr(OIDCService, "_get_jwks", fake_jwks)

    resp = await client.get(
        f"/v1/auth/sso/acme-oidc/callback?code=authcode&state={state}"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    claims = decode_token(body["access_token"])
    assert claims["role"] == "ADMIN"
    assert claims["organization_id"]

    me = await client.get("/v1/auth/me", headers=auth_headers(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "alice@corp.com"


async def test_oidc_callback_rejects_bad_state(client):
    token = await _superuser_token(client)
    await _create_oidc_connection(client, token)
    resp = await client.get(
        "/v1/auth/sso/acme-oidc/callback?code=authcode&state=does-not-exist"
    )
    assert resp.status_code == 422 or resp.status_code == 400


async def test_oidc_callback_rejects_nonce_mismatch(client, monkeypatch):
    token = await _superuser_token(client)
    created = await _create_oidc_connection(client, token)
    state = await create_state(created["id"], "expected-nonce", None)
    id_token = _id_token(
        issuer="https://idp.example.com",
        audience="client-123",
        sub="okta|x",
        email="bob@corp.com",
        nonce="WRONG-nonce",
    )

    async def fake_exchange(self, *, code, redirect_uri, code_verifier=None):
        return {"id_token": id_token}

    async def fake_jwks(self):
        return _jwks()

    monkeypatch.setattr(OIDCService, "exchange_code", fake_exchange)
    monkeypatch.setattr(OIDCService, "_get_jwks", fake_jwks)

    resp = await client.get(
        f"/v1/auth/sso/acme-oidc/callback?code=authcode&state={state}"
    )
    assert resp.status_code == 401


async def test_domain_restriction_blocks_foreign_email(client, monkeypatch):
    token = await _superuser_token(client)
    created = await _create_oidc_connection(
        client, token, allowed_email_domains=["corp.com"]
    )
    state = await create_state(created["id"], "n", None)
    id_token = _id_token(
        issuer="https://idp.example.com",
        audience="client-123",
        sub="okta|evil",
        email="mallory@evil.com",
        nonce="n",
    )

    async def fake_exchange(self, *, code, redirect_uri, code_verifier=None):
        return {"id_token": id_token}

    async def fake_jwks(self):
        return _jwks()

    monkeypatch.setattr(OIDCService, "exchange_code", fake_exchange)
    monkeypatch.setattr(OIDCService, "_get_jwks", fake_jwks)

    resp = await client.get(
        f"/v1/auth/sso/acme-oidc/callback?code=authcode&state={state}"
    )
    assert resp.status_code == 403


async def test_auto_provision_disabled_rejects_unknown_user(client, monkeypatch):
    token = await _superuser_token(client)
    created = await _create_oidc_connection(client, token, auto_provision=False)
    state = await create_state(created["id"], "n", None)
    id_token = _id_token(
        issuer="https://idp.example.com",
        audience="client-123",
        sub="okta|new",
        email="newcomer@corp.com",
        nonce="n",
    )

    async def fake_exchange(self, *, code, redirect_uri, code_verifier=None):
        return {"id_token": id_token}

    async def fake_jwks(self):
        return _jwks()

    monkeypatch.setattr(OIDCService, "exchange_code", fake_exchange)
    monkeypatch.setattr(OIDCService, "_get_jwks", fake_jwks)

    resp = await client.get(
        f"/v1/auth/sso/acme-oidc/callback?code=authcode&state={state}"
    )
    assert resp.status_code == 403


# --- organization mapping ---------------------------------------------------


async def test_organization_mapping_routes_to_mapped_org(client, monkeypatch):
    token = await _superuser_token(client)
    org = await create_organization(client, token, name="Acme Corp", slug="acme")
    created = await _create_oidc_connection(
        client,
        token,
        organization_id=None,
        organization_mappings={"acme.com": "acme"},
        allowed_email_domains=None,
    )
    state = await create_state(created["id"], "n", None)
    id_token = _id_token(
        issuer="https://idp.example.com",
        audience="client-123",
        sub="okta|mapped",
        email="carol@acme.com",
        nonce="n",
    )

    async def fake_exchange(self, *, code, redirect_uri, code_verifier=None):
        return {"id_token": id_token}

    async def fake_jwks(self):
        return _jwks()

    monkeypatch.setattr(OIDCService, "exchange_code", fake_exchange)
    monkeypatch.setattr(OIDCService, "_get_jwks", fake_jwks)

    resp = await client.get(
        f"/v1/auth/sso/acme-oidc/callback?code=authcode&state={state}"
    )
    assert resp.status_code == 200, resp.text
    claims = decode_token(resp.json()["access_token"])
    assert claims["organization_id"] == org["id"]


# --- SAML -------------------------------------------------------------------


async def _create_saml_connection(client, token, **overrides) -> dict:
    payload = {
        "slug": "acme-saml",
        "display_name": "Acme SAML",
        "protocol": "SAML",
        "provider": "GENERIC_SAML",
        "idp_entity_id": "https://idp.example.com/saml",
        "idp_sso_url": "https://idp.example.com/sso",
        "idp_x509_cert": _CERT_PEM,
        "sp_entity_id": "https://sp.nexora/acme",
        "role_mappings": {"engineering": "DEVELOPER"},
    }
    payload.update(overrides)
    resp = await client.post(
        "/v1/auth/sso/connections", headers=auth_headers(token), json=payload
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_saml_metadata_endpoint(client):
    token = await _superuser_token(client)
    await _create_saml_connection(client, token)
    resp = await client.get("/v1/auth/sso/acme-saml/metadata")
    assert resp.status_code == 200
    assert "EntityDescriptor" in resp.text
    assert "AssertionConsumerService" in resp.text


async def test_saml_acs_provisions_signed_assertion(client):
    token = await _superuser_token(client)
    await _create_saml_connection(client, token)
    acs_url = "http://test/nexora-api/v1/auth/sso/acme-saml/acs"
    saml_response = _build_signed_saml_response(
        issuer="https://idp.example.com/saml",
        sp_entity_id="https://sp.nexora/acme",
        acs_url=acs_url,
        name_id="dave@corp.com",
        email="dave@corp.com",
        name="Dave",
        groups=["engineering"],
    )
    resp = await client.post(
        "/v1/auth/sso/acme-saml/acs",
        data={"SAMLResponse": saml_response},
    )
    assert resp.status_code == 200, resp.text
    claims = decode_token(resp.json()["access_token"])
    assert claims["role"] == "DEVELOPER"

    me = await client.get(
        "/v1/auth/me", headers=auth_headers(resp.json()["access_token"])
    )
    assert me.json()["email"] == "dave@corp.com"


async def test_saml_acs_rejects_tampered_assertion(client):
    token = await _superuser_token(client)
    await _create_saml_connection(client, token)
    acs_url = "http://test/nexora-api/v1/auth/sso/acme-saml/acs"
    saml_response = _build_signed_saml_response(
        issuer="https://idp.example.com/saml",
        sp_entity_id="https://sp.nexora/acme",
        acs_url=acs_url,
        name_id="eve@corp.com",
        email="eve@corp.com",
    )
    raw = base64.b64decode(saml_response)
    tampered = raw.replace(b"eve@corp.com", b"admin@corp.com")
    resp = await client.post(
        "/v1/auth/sso/acme-saml/acs",
        data={"SAMLResponse": base64.b64encode(tampered).decode()},
    )
    assert resp.status_code == 401
