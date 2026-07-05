"""Unit tests for the Sprint 58A.1 real verification engine.

These exercise the engine in isolation (no DB, no real network): status mapping,
retry/backoff, timeout, unauthorized, partial, error mapping, per-provider
response parsing (mocked HTTP), JWT scope decoding, and secret-safety.
"""

import pytest

from app.services import integration_verification as iv
from app.services.integration_verification import (
    ProviderProbe,
    VStatus,
    _decode_jwt_claims,
    _Failed,
    _map_status,
    _Retryable,
    _Timeout,
    _Unauthorized,
    verify_provider,
)


# --------------------------- status mapping ------------------------------- #
async def test_unknown_provider_returns_failed():
    res = await verify_provider("NOPE", {})
    assert res.connection_status == VStatus.FAILED
    assert res.confidence == 0 and res.errors


async def test_connected_full_confidence(monkeypatch):
    async def _ok(secret):
        return ProviderProbe(identity={"account_id": "1"}, permissions=["sts:GetCallerIdentity"], version=None)

    monkeypatch.setitem(iv._VERIFIERS, "AWS", _ok)
    res = await verify_provider("AWS", {"access_key": "x"})
    assert res.connection_status == VStatus.CONNECTED
    assert res.confidence == 100 and res.errors == []
    assert res.provider_identity["account_id"] == "1"
    assert res.permissions == ["sts:GetCallerIdentity"]
    assert res.latency_ms >= 0


async def test_connected_with_warnings_drops_confidence(monkeypatch):
    async def _warn(secret):
        return ProviderProbe(identity={"x": "y"}, warnings=["minor"], partial=False)

    monkeypatch.setitem(iv._VERIFIERS, "AWS", _warn)
    res = await verify_provider("AWS", {})
    assert res.connection_status == VStatus.CONNECTED and res.confidence == 90


async def test_partial_status(monkeypatch):
    async def _partial(secret):
        return ProviderProbe(identity={"login": "octo"}, permissions=["repo"],
                             warnings=["Organizations not readable."], partial=True)

    monkeypatch.setitem(iv._VERIFIERS, "GITHUB", _partial)
    res = await verify_provider("GITHUB", {"token": "x"})
    assert res.connection_status == VStatus.PARTIAL and res.confidence == 60
    assert res.warnings


async def test_unauthorized_is_generic_and_secret_safe(monkeypatch):
    async def _unauth(secret):
        # A real verifier would raise this when the provider returns 401/403.
        raise _Unauthorized()

    monkeypatch.setitem(iv._VERIFIERS, "SLACK", _unauth)
    secret = {"bot_token": "xoxb-super-secret-value"}
    res = await verify_provider("SLACK", secret)
    assert res.connection_status == VStatus.UNAUTHORIZED and res.confidence == 0
    assert res.provider_identity == {} and res.permissions == []
    blob = " ".join(res.errors) + str(res.provider_identity) + str(res.warnings)
    assert "xoxb-super-secret-value" not in blob  # never leak the secret


async def test_failed_not_retried(monkeypatch):
    calls = {"n": 0}

    async def _fail(secret):
        calls["n"] += 1
        raise _Failed()

    monkeypatch.setattr(iv, "_RETRY_BASE_DELAY", 0)
    monkeypatch.setitem(iv._VERIFIERS, "JIRA", _fail)
    res = await verify_provider("JIRA", {})
    assert res.connection_status == VStatus.FAILED
    assert calls["n"] == 1  # deterministic failure is not retried


# --------------------------- retry / timeout ------------------------------ #
async def test_timeout_retries_then_times_out(monkeypatch):
    calls = {"n": 0}

    async def _always_timeout(secret):
        calls["n"] += 1
        raise _Timeout()

    monkeypatch.setattr(iv, "_RETRY_BASE_DELAY", 0)
    monkeypatch.setitem(iv._VERIFIERS, "AZURE", _always_timeout)
    res = await verify_provider("AZURE", {})
    assert res.connection_status == VStatus.TIMEOUT
    assert calls["n"] == iv._RETRY_ATTEMPTS  # retried up to the configured attempts


async def test_retryable_then_success(monkeypatch):
    calls = {"n": 0}

    async def _flaky(secret):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _Retryable()
        return ProviderProbe(identity={"ok": True})

    monkeypatch.setattr(iv, "_RETRY_BASE_DELAY", 0)
    monkeypatch.setitem(iv._VERIFIERS, "AWS", _flaky)
    res = await verify_provider("AWS", {})
    assert res.connection_status == VStatus.CONNECTED
    assert calls["n"] == 3


def test_map_status():
    for code in (401, 403):
        with pytest.raises(_Unauthorized):
            _map_status(code)
    for code in (429, 500, 503):
        with pytest.raises(_Retryable):
            _map_status(code)
    with pytest.raises(_Failed):
        _map_status(404)
    assert _map_status(200) is None  # 2xx -> no raise


# --------------------------- JWT scope decode ----------------------------- #
def test_decode_jwt_claims_reads_roles():
    import base64
    import json

    payload = base64.urlsafe_b64encode(
        json.dumps({"roles": ["Organization.Read.All"], "tid": "t1"}).encode()
    ).decode().rstrip("=")
    token = f"header.{payload}.sig"
    claims = _decode_jwt_claims(token)
    assert claims.get("roles") == ["Organization.Read.All"]
    assert _decode_jwt_claims("not-a-jwt") == {}


# --------------------------- per-provider parsing (mocked HTTP) ----------- #
def _fake_http(routes):
    """routes: list of (url_substring, response_dict). Returns an async fn."""
    async def _fn(method, url, *, headers=None, params=None, json_body=None, auth=None):
        for sub, resp in routes:
            if sub in url:
                if isinstance(resp, Exception):
                    raise resp
                return resp
        return {"_status": 200, "_headers": {}, "_json": {}}

    return _fn


async def test_slack_invalid_auth_maps_unauthorized(monkeypatch):
    monkeypatch.setattr(iv, "_http_request", _fake_http([
        ("auth.test", {"_status": 200, "_headers": {}, "_json": {"ok": False, "error": "invalid_auth"}}),
    ]))
    res = await verify_provider("SLACK", {"bot_token": "bad"})
    assert res.connection_status == VStatus.UNAUTHORIZED


async def test_slack_success_parses_identity(monkeypatch):
    monkeypatch.setattr(iv, "_http_request", _fake_http([
        ("auth.test", {"_status": 200, "_headers": {"x-oauth-scopes": "channels:read, chat:write"},
                       "_json": {"ok": True, "team": "Acme", "team_id": "T1", "user": "nexora",
                                 "bot_id": "B1", "url": "https://acme.slack.com"}}),
    ]))
    res = await verify_provider("SLACK", {"bot_token": "xoxb-good"})
    assert res.connection_status == VStatus.CONNECTED
    assert res.provider_identity["workspace"] == "Acme"
    assert res.provider_identity["team_id"] == "T1"
    assert res.permissions == ["channels:read", "chat:write"]


async def test_github_success_parses_scopes_and_orgs(monkeypatch):
    monkeypatch.setattr(iv, "_http_request", _fake_http([
        ("/user/orgs", {"_status": 200, "_headers": {}, "_json": [{"login": "acme"}]}),
        ("/user/repos", {"_status": 200, "_headers": {}, "_json": [{"id": 1}]}),
        ("/user", {"_status": 200, "_headers": {"x-oauth-scopes": "repo, read:org"},
                   "_json": {"login": "octocat", "id": 9, "name": "Octo"}}),
    ]))
    res = await verify_provider("GITHUB", {"token": "ghp_good"})
    assert res.connection_status == VStatus.CONNECTED
    assert res.provider_identity["login"] == "octocat"
    assert res.provider_identity["organizations"] == ["acme"]
    assert res.permissions == ["repo", "read:org"]


async def test_jira_success_parses_identity(monkeypatch):
    monkeypatch.setattr(iv, "_http_request", _fake_http([
        ("/rest/api/3/myself", {"_status": 200, "_headers": {},
                                "_json": {"accountId": "a1", "displayName": "Jane", "emailAddress": "j@x.io"}}),
        ("/rest/api/3/serverInfo", {"_status": 200, "_headers": {}, "_json": {"version": "1000.0.0"}}),
        ("/_edge/tenant_info", {"_status": 200, "_headers": {}, "_json": {"cloudId": "cloud-1"}}),
        ("/rest/api/3/project/search", {"_status": 200, "_headers": {}, "_json": {"total": 7}}),
        ("/rest/api/3/mypermissions", {"_status": 200, "_headers": {},
                                       "_json": {"permissions": {"BROWSE_PROJECTS": {"havePermission": True}}}}),
    ]))
    res = await verify_provider("JIRA", {"base_url": "https://x.atlassian.net", "email": "j@x.io",
                                         "api_token": "tok"})
    assert res.connection_status == VStatus.CONNECTED
    assert res.provider_identity["account_id"] == "a1"
    assert res.provider_identity["cloud_id"] == "cloud-1"
    assert res.provider_identity["project_count"] == 7
    assert "BROWSE_PROJECTS" in res.permissions


async def test_github_unauthorized_when_user_401(monkeypatch):
    monkeypatch.setattr(iv, "_http_request", _fake_http([
        ("/user", _Unauthorized()),
    ]))
    res = await verify_provider("GITHUB", {"token": "bad"})
    assert res.connection_status == VStatus.UNAUTHORIZED
