"""Sprint 35B — Bring Your Own Infrastructure (BYOI) wizard tests.

Covers connection verification, status, readiness score, pre-deployment
validation, customer-safe guidance (no stack traces), audit, and tenancy.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.infrastructure.validator import CheckResult
from app.infrastructure.validator import _safe as safe_check
from app.models.credential import SecretAccessAudit
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    switch_organization,
)

SECRETS = {
    "AZURE": {
        "subscription_id": "sub-1",
        "tenant_id": "ten-1",
        "client_id": "cli-1",
        "client_secret": "SECRET-AZURE",
    },
    "AWS": {"access_key": "AKIA", "secret_key": "SECRET-AWS", "region": "us-east-1"},
    "KUBERNETES": {"kubeconfig": "apiVersion: v1\nclusters: []\n"},
    "VM": {
        "host": "10.0.0.5",
        "port": 22,
        "username": "ubuntu",
        "private_key": "-----BEGIN PRIVATE KEY-----SECRETKEY-----END PRIVATE KEY-----",
    },
}

CHECK_NAMES = {
    "AZURE": ["Subscription access", "Resource group access", "Deployment permissions"],
    "AWS": ["Account access", "Region access", "Deployment permissions"],
    "KUBERNETES": ["Cluster reachable", "Namespace access", "Create deployment permission"],
    "VM": ["SSH reachable", "Docker installed", "Docker Compose installed"],
}


def _all_pass(provider):
    return lambda secret: [CheckResult(n, True, "ok") for n in CHECK_NAMES[provider]]


def _partial(provider):
    names = CHECK_NAMES[provider]
    return lambda secret: [
        CheckResult(names[0], True, "ok"),
        CheckResult(names[1], True, "ok"),
        CheckResult(names[2], False, "permission missing"),
    ]


async def _org_user(client, *, email, slug):
    _, tokens = await create_authenticated_user(client, email=email, username=slug.replace("-", "_"))
    org = await create_organization(client, tokens["access_token"], name=slug, slug=slug)
    tokens = await switch_organization(client, tokens["access_token"], org["id"])
    return tokens, org["id"]


async def _create(client, token, provider):
    resp = await client.post(
        "/v1/credentials",
        headers=auth_headers(token),
        json={"provider": provider, "name": f"{provider} prod", "secret": SECRETS[provider]},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _patch(provider, probe_factory):
    return patch.dict(
        "app.infrastructure.validator.DEFAULT_PROBES",
        {provider: probe_factory(provider)},
        clear=False,
    )


# --------------------------------------------------------------------------- #
# Verification + status + score
# --------------------------------------------------------------------------- #
async def test_create_sets_connected_status(client):
    tokens, _ = await _org_user(client, email="w1@x.com", slug="byoi-1")
    cred_id = await _create(client, tokens["access_token"], "AZURE")
    got = await client.get(f"/v1/credentials/{cred_id}", headers=auth_headers(tokens["access_token"]))
    body = got.json()
    assert body["status"] == "CONNECTED"
    assert body["readiness_score"] == 0
    assert body["last_verified_at"] is None


@pytest.mark.parametrize("provider", ["AZURE", "AWS", "KUBERNETES", "VM"])
async def test_verify_marks_verified_full_score(client, provider):
    tokens, _ = await _org_user(client, email=f"wv-{provider}@x.com", slug=f"byoi-v-{provider.lower()}")
    token = tokens["access_token"]
    cred_id = await _create(client, token, provider)
    with _patch(provider, _all_pass):
        resp = await client.post(f"/v1/credentials/{cred_id}/verify", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ready"] is True
    assert body["readiness_score"] == 100
    assert body["status"] == "VERIFIED"
    assert len(body["checks"]) == 3
    # no secret material leaks into the verification response
    assert "SECRET-" not in resp.text and "BEGIN PRIVATE KEY" not in resp.text


async def test_verify_marks_failed_partial_score(client):
    tokens, _ = await _org_user(client, email="wf@x.com", slug="byoi-fail")
    token = tokens["access_token"]
    cred_id = await _create(client, token, "KUBERNETES")
    with _patch("KUBERNETES", _partial):
        resp = await client.post(f"/v1/credentials/{cred_id}/verify", headers=auth_headers(token))
    body = resp.json()
    assert body["ready"] is False
    assert body["readiness_score"] == 67
    assert body["status"] == "VERIFICATION_FAILED"
    assert "Action needed" in body["guidance"]


async def test_status_endpoint_reflects_verification(client):
    tokens, _ = await _org_user(client, email="ws@x.com", slug="byoi-status")
    token = tokens["access_token"]
    cred_id = await _create(client, token, "VM")
    with _patch("VM", _all_pass):
        await client.post(f"/v1/credentials/{cred_id}/verify", headers=auth_headers(token))
    status_resp = await client.get(f"/v1/credentials/{cred_id}/status", headers=auth_headers(token))
    body = status_resp.json()
    assert body["status"] == "VERIFIED"
    assert body["readiness_score"] == 100
    assert body["last_verified_at"] is not None
    assert "BEGIN PRIVATE KEY" not in status_resp.text


# --------------------------------------------------------------------------- #
# Pre-deployment validation + customer-safe guidance
# --------------------------------------------------------------------------- #
async def test_validate_for_deploy_ready(client):
    tokens, _ = await _org_user(client, email="wd@x.com", slug="byoi-deploy")
    token = tokens["access_token"]
    cred_id = await _create(client, token, "AZURE")
    with _patch("AZURE", _all_pass):
        resp = await client.post(f"/v1/credentials/{cred_id}/validate", headers=auth_headers(token))
    body = resp.json()
    assert body["ready"] is True
    assert "ready for deployment" in body["guidance"].lower()


async def test_customer_safe_no_stack_trace(client):
    """A probe that raises must surface a friendly message, never an exception."""
    tokens, _ = await _org_user(client, email="wc@x.com", slug="byoi-safe")
    token = tokens["access_token"]
    cred_id = await _create(client, token, "VM")

    def raising_probe(secret):
        def boom():
            raise RuntimeError("paramiko.ssh_exception.AuthenticationException: secret leaked here")

        return [
            safe_check("SSH reachable", boom, "Could not connect with the supplied credentials."),
            CheckResult("Docker installed", False, "Could not confirm Docker on the VM."),
            CheckResult("Docker Compose installed", False, "Could not confirm Docker Compose on the VM."),
        ]

    with patch.dict("app.infrastructure.validator.DEFAULT_PROBES", {"VM": raising_probe}, clear=False):
        resp = await client.post(f"/v1/credentials/{cred_id}/validate", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ready"] is False
    # Never expose raw exception/stack trace content to the customer.
    assert "paramiko" not in resp.text
    assert "AuthenticationException" not in resp.text
    assert "Traceback" not in resp.text
    assert "secret leaked here" not in resp.text


def test_safe_swallows_exception_unit():
    def boom():
        raise ValueError("raw provider error 0xdeadbeef")

    result = safe_check("Subscription access", boom, "Could not connect.")
    assert result.passed is False
    assert "0xdeadbeef" not in result.message
    assert result.message == "Could not connect."


# --------------------------------------------------------------------------- #
# Audit + revocation + tenancy
# --------------------------------------------------------------------------- #
async def test_verify_audits_secret_used(client):
    from app.database.session import AsyncSessionLocal

    tokens, _ = await _org_user(client, email="wa@x.com", slug="byoi-audit")
    token = tokens["access_token"]
    cred_id = await _create(client, token, "AZURE")
    with _patch("AZURE", _all_pass):
        await client.post(f"/v1/credentials/{cred_id}/verify", headers=auth_headers(token))
    async with AsyncSessionLocal() as session:
        used = (
            await session.execute(
                select(SecretAccessAudit).where(
                    SecretAccessAudit.credential_id == cred_id,
                    SecretAccessAudit.event == "SECRET_USED",
                )
            )
        ).scalars().all()
        assert used
        assert any("verification" in (u.reason or "") for u in used)


async def test_revoked_credential_cannot_verify(client):
    tokens, _ = await _org_user(client, email="wr@x.com", slug="byoi-revoke")
    token = tokens["access_token"]
    cred_id = await _create(client, token, "AZURE")
    await client.put(
        f"/v1/credentials/{cred_id}", headers=auth_headers(token), json={"is_active": False}
    )
    with _patch("AZURE", _all_pass):
        resp = await client.post(f"/v1/credentials/{cred_id}/verify", headers=auth_headers(token))
    assert resp.status_code == 422


async def test_tenancy_isolation_verify(client):
    a_tokens, _ = await _org_user(client, email="wta@x.com", slug="byoi-ta")
    b_tokens, _ = await _org_user(client, email="wtb@x.com", slug="byoi-tb")
    cred_id = await _create(client, a_tokens["access_token"], "AZURE")

    for path, method in (
        (f"/v1/credentials/{cred_id}/verify", "post"),
        (f"/v1/credentials/{cred_id}/validate", "post"),
        (f"/v1/credentials/{cred_id}/status", "get"),
    ):
        caller = getattr(client, method)
        resp = await caller(path, headers=auth_headers(b_tokens["access_token"]))
        assert resp.status_code == 404, f"{path} -> {resp.status_code}"
