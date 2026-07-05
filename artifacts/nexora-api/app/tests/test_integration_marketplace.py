"""Tests for the Integration Marketplace.

Sprint 47B covered catalogue/connect/list/disconnect/isolation/audit.
Sprint 58A.1 replaces the previous configuration-only ("simulated") verification
with REAL provider verification. The verify tests here mock the network boundary
(``verify_provider``) so they assert the *marketplace's* behaviour deterministically:
that it only marks a connection VERIFIED/HEALTHY when the provider confirms it,
maps every status correctly, surfaces the rich result, never leaks secrets, and
audits started/finished/failed. The real provider probes themselves are unit
tested in ``test_integration_verification.py``.
"""

from datetime import UTC, datetime

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.services import integration_marketplace as mp
from app.services.integration_verification import VerificationResult, VStatus
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers

SUPPORTED = {
    "AWS", "AZURE", "KUBERNETES", "GITHUB", "GITLAB", "BITBUCKET", "JIRA",
    "DATADOG", "PROMETHEUS", "GRAFANA", "NEW_RELIC", "PAGERDUTY", "SLACK",
    "MICROSOFT_TEAMS",
    "GCP", "CLOUDWATCH", "ARGOCD", "TERRAFORM", "JENKINS", "AZURE_DEVOPS",
    "CIRCLECI", "HASHICORP_VAULT", "LOKI", "ELASTIC", "OPSGENIE", "SONARQUBE",
}


async def _connect(client, token, key, creds, name=None):
    body = {"integration_key": key, "credentials": creds}
    if name:
        body["name"] = name
    return await client.post("/v1/integrations/connect", headers=H(token), json=body)


AWS_CREDS = {"access_key": "AKIA...", "secret_key": "shh", "region": "us-east-1"}
SLACK_CREDS = {"bot_token": "xoxb-secret-123"}


def _result(status, *, identity=None, permissions=None, version=None,
            warnings=None, errors=None, confidence=None, latency=42):
    """Build a VerificationResult mirroring what verify_provider would return."""
    conf = confidence
    if conf is None:
        conf = 100 if status == VStatus.CONNECTED else (60 if status == VStatus.PARTIAL else 0)
    return VerificationResult(
        connection_status=status, latency_ms=latency, provider_version=version,
        verified_at=datetime.now(UTC), provider_identity=identity or {},
        permissions=permissions or [], warnings=warnings or [], errors=errors or [],
        confidence=conf,
    )


def _patch_verify(monkeypatch, result_or_fn):
    """Patch the verify_provider symbol used inside the marketplace service."""
    async def _fake(integration_key, secret):
        if callable(result_or_fn):
            return result_or_fn(integration_key, secret)
        return result_or_fn
    monkeypatch.setattr(mp, "verify_provider", _fake)


# ============================== catalogue ================================ #
async def test_marketplace_lists_supported(client):
    _, t = await create_authenticated_user(client, email="im1@e.com", username="im1")
    token = t["access_token"]
    r = await client.get("/v1/integrations", headers=H(token))
    assert r.status_code == 200, r.text
    body = r.json()
    keys = {i["integration_key"] for i in body["integrations"]}
    assert SUPPORTED <= keys
    assert body["summary"]["supported"] == len(body["integrations"])
    assert body["summary"]["connected"] == 0
    aws = next(i for i in body["integrations"] if i["integration_key"] == "AWS")
    assert aws["required_fields"] == ["access_key", "secret_key", "region"]
    assert aws["capabilities"] and aws["connected"] is False
    # Sprint 58A.1: Teams now uses Graph app credentials (not a webhook).
    teams = next(i for i in body["integrations"] if i["integration_key"] == "MICROSOFT_TEAMS")
    assert teams["required_fields"] == ["tenant_id", "client_id", "client_secret"]


# ============================== connect ================================== #
async def test_connect_reuses_credential_framework(client):
    _, t = await create_authenticated_user(client, email="im2@e.com", username="im2")
    token = t["access_token"]
    r = await _connect(client, token, "AWS", AWS_CREDS)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["integration_key"] == "AWS"
    # Connecting NEVER pre-marks a connection healthy/verified.
    assert c["status"] == "CONNECTED" and c["health"] == "UNKNOWN"
    assert "credentials" not in c and "secret_key" not in r.text
    conns = (await client.get("/v1/integrations/connections", headers=H(token))).json()
    assert len(conns) == 1 and conns[0]["integration_key"] == "AWS"
    creds = (await client.get("/v1/credentials", headers=H(token))).json()
    assert creds["total"] >= 1


async def test_connect_missing_fields_rejected(client):
    _, t = await create_authenticated_user(client, email="im3@e.com", username="im3")
    token = t["access_token"]
    r = await _connect(client, token, "AWS", {"access_key": "only"})
    assert r.status_code == 422


async def test_connect_unsupported_rejected(client):
    _, t = await create_authenticated_user(client, email="im4@e.com", username="im4")
    token = t["access_token"]
    r = await _connect(client, token, "NOT_A_THING", {"x": "y"})
    assert r.status_code == 422


async def test_rotate_connection_credentials(client):
    _, t = await create_authenticated_user(client, email="im4r@e.com", username="im4r")
    token = t["access_token"]
    conn = (await _connect(client, token, "AWS", AWS_CREDS)).json()
    rotated = {
        "access_key": "AKIAROTATED",
        "secret_key": "new-secret",
        "region": "eu-west-1",
    }
    r = await client.put(
        f"/v1/integrations/connections/{conn['id']}/credentials",
        headers=H(token),
        json={"credentials": rotated},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == conn["id"]
    assert "secret_key" not in r.text
    assert "new-secret" not in r.text


# ============================== verify: real success ===================== #
async def test_verify_connected_marks_verified_with_real_result(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="im5@e.com", username="im5")
    token = t["access_token"]
    conn = (await _connect(client, token, "SLACK", SLACK_CREDS)).json()
    _patch_verify(monkeypatch, _result(
        VStatus.CONNECTED,
        identity={"workspace": "Acme", "team_id": "T123", "bot_user": "nexora"},
        permissions=["channels:read", "chat:write"], version=None, latency=87,
    ))
    r = await client.post("/v1/integrations/verify", headers=H(token), json={"connection_id": conn["id"]})
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["verified"] is True and v["status"] == "VERIFIED" and v["health"] == "HEALTHY"
    assert v["connection_status"] == "CONNECTED"
    assert v["readiness_score"] == 100 and v["confidence"] == 100
    assert v["permissions_granted"] == ["channels:read", "chat:write"]
    assert v["provider_identity"]["workspace"] == "Acme"
    assert v["latency_ms"] == 87 and v["verified_at"]
    assert {"Credentials configured", "Connectivity (read-only)", "Read permissions"} <= {
        c["name"] for c in v["checks"]}
    assert "xoxb-secret-123" not in r.text
    # connection now reflects verified state + last_sync + rich fields
    conns = (await client.get("/v1/integrations/connections", headers=H(token))).json()
    got = conns[0]
    assert got["status"] == "VERIFIED" and got["last_verified_at"] and got["last_sync_at"]
    assert got["connection_status"] == "CONNECTED" and got["permissions_granted"]
    assert got["provider_identity"]["team_id"] == "T123"


# ============================== verify: NOT healthy without provider ===== #
async def test_verify_unauthorized_is_not_marked_healthy(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="im5u@e.com", username="im5u")
    token = t["access_token"]
    conn = (await _connect(client, token, "AWS", AWS_CREDS)).json()
    _patch_verify(monkeypatch, _result(
        VStatus.UNAUTHORIZED,
        errors=["Authentication failed: the provider rejected the supplied credentials."],
    ))
    r = await client.post("/v1/integrations/verify", headers=H(token), json={"connection_id": conn["id"]})
    v = r.json()
    assert v["verified"] is False
    assert v["status"] == "NEEDS_ATTENTION" and v["health"] == "UNHEALTHY"
    assert v["connection_status"] == "UNAUTHORIZED"
    assert v["readiness_score"] == 0 and v["confidence"] == 0
    assert v["permissions_granted"] == []
    assert any("Authentication failed" in e for e in v["errors"])
    conns = (await client.get("/v1/integrations/connections", headers=H(token))).json()
    assert conns[0]["status"] != "VERIFIED" and conns[0]["health"] != "HEALTHY"
    assert conns[0]["last_sync_at"] is None


async def test_verify_timeout_status(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="im5t@e.com", username="im5t")
    token = t["access_token"]
    conn = (await _connect(client, token, "GITHUB", {"token": "ghp_x"})).json()
    _patch_verify(monkeypatch, _result(
        VStatus.TIMEOUT, errors=["The provider did not respond within the allowed time."]))
    v = (await client.post("/v1/integrations/verify", headers=H(token),
                           json={"connection_id": conn["id"]})).json()
    assert v["verified"] is False and v["connection_status"] == "TIMEOUT"
    assert v["status"] == "NEEDS_ATTENTION" and v["health"] == "UNKNOWN"


async def test_verify_partial_status(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="im5p@e.com", username="im5p")
    token = t["access_token"]
    conn = (await _connect(client, token, "GITHUB", {"token": "ghp_x"})).json()
    _patch_verify(monkeypatch, _result(
        VStatus.PARTIAL, identity={"login": "octo"}, permissions=["repo"],
        warnings=["Organizations not readable with this token."]))
    v = (await client.post("/v1/integrations/verify", headers=H(token),
                           json={"connection_id": conn["id"]})).json()
    assert v["verified"] is False and v["connection_status"] == "PARTIAL"
    assert v["status"] == "NEEDS_ATTENTION" and v["health"] == "DEGRADED"
    assert v["confidence"] == 60 and v["warnings"]


async def test_verify_failed_provider_error(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="im5f@e.com", username="im5f")
    token = t["access_token"]
    conn = (await _connect(client, token, "JIRA",
                           {"base_url": "https://x.atlassian.net", "email": "a@b.c", "api_token": "tok"})).json()
    _patch_verify(monkeypatch, _result(
        VStatus.FAILED, errors=["Could not complete verification against the provider."]))
    v = (await client.post("/v1/integrations/verify", headers=H(token),
                           json={"connection_id": conn["id"]})).json()
    assert v["verified"] is False and v["connection_status"] == "FAILED"
    assert v["status"] == "NEEDS_ATTENTION"


async def test_verify_unknown_connection_404(client):
    _, t = await create_authenticated_user(client, email="im6@e.com", username="im6")
    token = t["access_token"]
    r = await client.post("/v1/integrations/verify", headers=H(token), json={"connection_id": "nope"})
    assert r.status_code == 404


# ============================== rollup + disconnect ====================== #
async def test_marketplace_rollup_and_disconnect(client, monkeypatch):
    _, t = await create_authenticated_user(client, email="im7@e.com", username="im7")
    token = t["access_token"]
    _patch_verify(monkeypatch, _result(VStatus.CONNECTED, identity={"account_id": "123"},
                                        permissions=["sts:GetCallerIdentity"]))
    conn = (await _connect(client, token, "AWS", AWS_CREDS)).json()
    await client.post("/v1/integrations/verify", headers=H(token), json={"connection_id": conn["id"]})
    body = (await client.get("/v1/integrations", headers=H(token))).json()
    assert body["summary"]["connected"] == 1 and body["summary"]["verified"] == 1
    aws = next(i for i in body["integrations"] if i["integration_key"] == "AWS")
    assert aws["connected"] is True and aws["status"] == "VERIFIED"
    d = await client.delete(f"/v1/integrations/connections/{conn['id']}", headers=H(token))
    assert d.status_code == 204
    assert (await client.get("/v1/integrations/connections", headers=H(token))).json() == []
    body2 = (await client.get("/v1/integrations", headers=H(token))).json()
    assert body2["summary"]["connected"] == 0
    v = await client.post("/v1/integrations/verify", headers=H(token), json={"connection_id": conn["id"]})
    assert v.status_code == 404


# ============================== isolation ================================ #
async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="imA@e.com", username="imA")
    _, t2 = await create_authenticated_user(client, email="imB@e.com", username="imB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    conn = (await _connect(client, tok1, "GITHUB", {"token": "ghp_secret"})).json()
    body2 = (await client.get("/v1/integrations", headers=H(tok2))).json()
    assert body2["summary"]["connected"] == 0
    assert (await client.get("/v1/integrations/connections", headers=H(tok2))).json() == []
    # Cross-tenant verify is rejected BEFORE any provider call (404, never leaks).
    assert (await client.post("/v1/integrations/verify", headers=H(tok2),
                              json={"connection_id": conn["id"]})).status_code == 404
    assert (await client.delete(f"/v1/integrations/connections/{conn['id']}",
                                headers=H(tok2))).status_code == 404


# ============================== credential safety ======================== #
async def test_verify_without_credential_fails_safely(client, monkeypatch):
    """If the credential cannot be resolved, the provider is never called and the
    connection is reported FAILED (never VERIFIED)."""
    _, t = await create_authenticated_user(client, email="imC@e.com", username="imC")
    token = t["access_token"]
    conn = (await _connect(client, token, "AWS", AWS_CREDS)).json()
    called = {"n": 0}

    async def _should_not_run(integration_key, secret):  # pragma: no cover - asserted not called
        called["n"] += 1
        return _result(VStatus.CONNECTED)

    async def _resolve_raises(*args, **kwargs):
        raise RuntimeError("credential revoked")

    monkeypatch.setattr(mp, "verify_provider", _should_not_run)
    monkeypatch.setattr(mp.SecretManagerService, "resolve_secret", _resolve_raises)
    v = (await client.post("/v1/integrations/verify", headers=H(token),
                           json={"connection_id": conn["id"]})).json()
    assert v["verified"] is False and v["connection_status"] == "FAILED"
    assert called["n"] == 0  # provider never contacted without a credential


# ============================== audit ==================================== #
async def test_audit_logging(client, monkeypatch):
    me, t = await create_authenticated_user(client, email="im8@e.com", username="im8")
    token = t["access_token"]
    _patch_verify(monkeypatch, _result(VStatus.CONNECTED, identity={"x": "y"}, permissions=["p"]))
    await client.get("/v1/integrations", headers=H(token))
    conn = (await _connect(client, token, "PAGERDUTY", {"api_key": "pd-secret"})).json()
    await client.post("/v1/integrations/verify", headers=H(token), json={"connection_id": conn["id"]})
    await client.delete(f"/v1/integrations/connections/{conn['id']}", headers=H(token))
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    # Backward-compatible action names plus the new lifecycle events.
    assert {"integration_marketplace_viewed", "integration_connected",
            "integration_verified", "integration_disconnected",
            "integration_verification_started", "integration_verification_finished"} <= actions
