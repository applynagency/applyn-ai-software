"""Enterprise identity & access platform tests (Sprint 61A).

Covers API keys (personal/org/service-account), service accounts, database-backed
sessions, organization security policies, MFA (TOTP + recovery codes) and the SSO
extensions (Auth0/Keycloak presets, SAML metadata import, certificate rotation).
"""

from __future__ import annotations

import pytest

from app.services.identity import scopes as scope_lib
from app.services.identity import totp as totp_lib

from .conftest import auth_headers, create_authenticated_user


async def _auth(client, email="id_user@example.com", username="id_user"):
    me, tokens = await create_authenticated_user(
        client, email=email, username=username
    )
    return me, tokens["access_token"]


# --- API keys ----------------------------------------------------------------


async def test_personal_api_key_lifecycle_and_auth(client):
    _, token = await _auth(client)
    h = auth_headers(token)

    created = await client.post(
        "/v1/api-keys/personal",
        json={"name": "ci", "scopes": ["incidents:read"]},
        headers=h,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["api_key"].startswith("nxk_")
    assert body["prefix"].startswith("nxk_")
    assert "hashed_key" not in body
    plaintext = body["api_key"]

    # The personal key authenticates as the owning user on a user endpoint.
    me = await client.get("/v1/auth/me", headers=auth_headers(plaintext))
    assert me.status_code == 200, me.text
    assert me.json()["email"] == "id_user@example.com"

    # whoami reports the principal.
    who = await client.get("/v1/identity/whoami", headers=auth_headers(plaintext))
    assert who.status_code == 200
    assert who.json()["principal_type"] == "USER"

    listed = await client.get("/v1/api-keys/personal", headers=h)
    assert listed.json()["total"] == 1

    # Rotation invalidates the old secret and returns a new one.
    rotated = await client.post(
        f"/v1/api-keys/personal/{body['id']}/rotate", headers=h
    )
    assert rotated.status_code == 200
    new_secret = rotated.json()["api_key"]
    assert new_secret != plaintext
    old = await client.get("/v1/auth/me", headers=auth_headers(plaintext))
    assert old.status_code == 401
    fresh = await client.get("/v1/auth/me", headers=auth_headers(new_secret))
    assert fresh.status_code == 200

    # Revoke the rotated key.
    revoke = await client.delete(
        f"/v1/api-keys/personal/{rotated.json()['id']}", headers=h
    )
    assert revoke.status_code == 204
    dead = await client.get("/v1/auth/me", headers=auth_headers(new_secret))
    assert dead.status_code == 401


async def test_organization_api_key(client):
    _, token = await _auth(client, "orgkey@example.com", "orgkey")
    h = auth_headers(token)
    created = await client.post(
        "/v1/api-keys/organization", json={"name": "svc"}, headers=h
    )
    assert created.status_code == 201, created.text
    key = created.json()["api_key"]

    # Org keys are machine principals — not valid for interactive user access.
    me = await client.get("/v1/auth/me", headers=auth_headers(key))
    assert me.status_code == 403

    who = await client.get("/v1/identity/whoami", headers=auth_headers(key))
    assert who.status_code == 200
    assert who.json()["principal_type"] == "ORGANIZATION"
    assert who.json()["organization_id"]


async def test_invalid_api_key_rejected(client):
    who = await client.get(
        "/v1/identity/whoami", headers=auth_headers("nxk_not_a_real_key")
    )
    assert who.status_code == 401


# --- Service accounts --------------------------------------------------------


async def test_service_account_and_key(client):
    _, token = await _auth(client, "sa@example.com", "sauser")
    h = auth_headers(token)

    created = await client.post(
        "/v1/service-accounts",
        json={"name": "deployer", "role": "DEVELOPER", "scopes": ["deployments:write"]},
        headers=h,
    )
    assert created.status_code == 201, created.text
    sa_id = created.json()["id"]

    key_resp = await client.post(
        f"/v1/service-accounts/{sa_id}/keys", json={"name": "primary"}, headers=h
    )
    assert key_resp.status_code == 201, key_resp.text
    sa_key = key_resp.json()["api_key"]

    who = await client.get("/v1/identity/whoami", headers=auth_headers(sa_key))
    assert who.status_code == 200
    assert who.json()["principal_type"] == "SERVICE_ACCOUNT"
    assert who.json()["service_account_id"] == sa_id
    assert who.json()["role"] == "DEVELOPER"

    # Disabling the account revokes its keys.
    disabled = await client.post(
        f"/v1/service-accounts/{sa_id}/disable", headers=h
    )
    assert disabled.status_code == 200
    assert disabled.json()["disabled"] is True
    dead = await client.get("/v1/identity/whoami", headers=auth_headers(sa_key))
    assert dead.status_code == 401


# --- Sessions ----------------------------------------------------------------


async def test_sessions_list_and_logout_all(client):
    await create_authenticated_user(client, email="sess@example.com", username="sess")
    # A second login creates a second device session.
    t1 = (await client.post(
        "/v1/auth/login", json={"email": "sess@example.com", "password": "password123"}
    )).json()
    t2 = (await client.post(
        "/v1/auth/login", json={"email": "sess@example.com", "password": "password123"}
    )).json()

    listed = await client.get("/v1/sessions", headers=auth_headers(t2["access_token"]))
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] >= 2
    assert any(s["current"] for s in listed.json()["items"])

    out = await client.post(
        "/v1/sessions/logout-all", headers=auth_headers(t2["access_token"])
    )
    assert out.status_code == 200
    assert out.json()["revoked"] >= 1

    remaining = await client.get(
        "/v1/sessions", headers=auth_headers(t2["access_token"])
    )
    # Only the current session survives logout-all.
    assert remaining.json()["total"] == 1


# --- Security policy ---------------------------------------------------------


async def test_security_policy_get_and_update(client):
    _, token = await _auth(client, "policy@example.com", "policyuser")
    h = auth_headers(token)

    got = await client.get("/v1/security-policy", headers=h)
    assert got.status_code == 200, got.text
    assert got.json()["password_min_length"] == 12

    updated = await client.put(
        "/v1/security-policy",
        json={
            "password_min_length": 16,
            "mfa_required": True,
            "max_concurrent_sessions": 3,
            "ip_allowlist": ["10.0.0.0/8"],
        },
        headers=h,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["password_min_length"] == 16
    assert updated.json()["mfa_required"] is True
    assert updated.json()["ip_allowlist"] == ["10.0.0.0/8"]


async def test_security_policy_rejects_bad_cidr(client):
    _, token = await _auth(client, "policy2@example.com", "policy2")
    bad = await client.put(
        "/v1/security-policy",
        json={"ip_allowlist": ["not-a-cidr"]},
        headers=auth_headers(token),
    )
    assert bad.status_code == 400


# --- MFA ---------------------------------------------------------------------


async def test_mfa_enroll_confirm_and_enforced_login(client):
    _, token = await _auth(client, "mfa@example.com", "mfauser")
    h = auth_headers(token)

    status = await client.get("/v1/auth/mfa/status", headers=h)
    assert status.json()["enabled"] is False

    enroll = await client.post("/v1/auth/mfa/enroll", headers=h)
    assert enroll.status_code == 200, enroll.text
    secret = enroll.json()["secret"]
    assert enroll.json()["otpauth_uri"].startswith("otpauth://totp/")

    # Confirm with a valid generated code → returns recovery codes.
    code = totp_lib.generate_totp(secret)
    confirm = await client.post(
        "/v1/auth/mfa/confirm", json={"code": code}, headers=h
    )
    assert confirm.status_code == 200, confirm.text
    recovery_codes = confirm.json()["recovery_codes"]
    assert len(recovery_codes) == 10

    status2 = await client.get("/v1/auth/mfa/status", headers=h)
    assert status2.json()["enabled"] is True
    assert status2.json()["recovery_codes_remaining"] == 10

    # Login now requires the second factor.
    no_code = await client.post(
        "/v1/auth/login", json={"email": "mfa@example.com", "password": "password123"}
    )
    assert no_code.status_code == 401

    wrong = await client.post(
        "/v1/auth/login",
        json={"email": "mfa@example.com", "password": "password123", "mfa_code": "000000"},
    )
    assert wrong.status_code == 401

    good = await client.post(
        "/v1/auth/login",
        json={
            "email": "mfa@example.com",
            "password": "password123",
            "mfa_code": totp_lib.generate_totp(secret),
        },
    )
    assert good.status_code == 200, good.text

    # A recovery code also satisfies the second factor (single use).
    rec = recovery_codes[0]
    rec_login = await client.post(
        "/v1/auth/login",
        json={"email": "mfa@example.com", "password": "password123", "mfa_code": rec},
    )
    assert rec_login.status_code == 200
    reused = await client.post(
        "/v1/auth/login",
        json={"email": "mfa@example.com", "password": "password123", "mfa_code": rec},
    )
    assert reused.status_code == 401


async def test_mfa_disable(client):
    _, token = await _auth(client, "mfa2@example.com", "mfa2")
    h = auth_headers(token)
    enroll = await client.post("/v1/auth/mfa/enroll", headers=h)
    secret = enroll.json()["secret"]
    await client.post(
        "/v1/auth/mfa/confirm",
        json={"code": totp_lib.generate_totp(secret)},
        headers=h,
    )
    disabled = await client.post("/v1/auth/mfa/disable", headers=h)
    assert disabled.status_code == 204
    status = await client.get("/v1/auth/mfa/status", headers=h)
    assert status.json()["enabled"] is False
    # Login no longer requires a code.
    login = await client.post(
        "/v1/auth/login", json={"email": "mfa2@example.com", "password": "password123"}
    )
    assert login.status_code == 200


# --- scope catalog -----------------------------------------------------------


async def test_scope_catalog(client):
    _, token = await _auth(client, "scopes@example.com", "scopesuser")
    resp = await client.get("/v1/identity/scopes", headers=auth_headers(token))
    assert resp.status_code == 200
    assert "*" in resp.json()["scopes"]


def test_scope_helpers():
    assert scope_lib.has_scope(["*"], "incidents:read")
    assert scope_lib.has_scope(["incidents:write"], "incidents:read")
    assert not scope_lib.has_scope(["incidents:read"], "incidents:write")
    assert scope_lib.validate_scopes(None) == ["*"]
    with pytest.raises(ValueError):
        scope_lib.validate_scopes(["bogus:scope"])


# --- TOTP unit ---------------------------------------------------------------


def test_totp_roundtrip():
    secret = totp_lib.generate_secret()
    code = totp_lib.generate_totp(secret)
    assert totp_lib.verify_totp(secret, code)
    assert not totp_lib.verify_totp(secret, "123456", valid_window=0) or code == "123456"


# --- SSO extensions ----------------------------------------------------------


def test_sso_presets_include_auth0_and_keycloak():
    from app.models.sso import SSOProvider
    from app.services.sso import presets

    assert SSOProvider.AUTH0.value in presets.PROVIDER_DEFAULTS
    assert SSOProvider.KEYCLOAK.value in presets.PROVIDER_DEFAULTS
    assert hasattr(SSOProvider, "ONELOGIN")


def test_saml_metadata_import_parsing():
    from app.services.sso.saml import parse_idp_metadata

    metadata = """<?xml version="1.0"?>
    <md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
        xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
        entityID="https://idp.example.com/entity">
      <md:IDPSSODescriptor protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
        <md:KeyDescriptor use="signing">
          <ds:KeyInfo><ds:X509Data><ds:X509Certificate>MIIBfakeCERT</ds:X509Certificate></ds:X509Data></ds:KeyInfo>
        </md:KeyDescriptor>
        <md:SingleLogoutService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            Location="https://idp.example.com/slo"/>
        <md:SingleSignOnService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            Location="https://idp.example.com/sso"/>
      </md:IDPSSODescriptor>
    </md:EntityDescriptor>"""
    parsed = parse_idp_metadata(metadata)
    assert parsed["idp_entity_id"] == "https://idp.example.com/entity"
    assert parsed["idp_sso_url"] == "https://idp.example.com/sso"
    assert parsed["logout_url"] == "https://idp.example.com/slo"
    assert parsed["idp_x509_cert"] == "MIIBfakeCERT"
