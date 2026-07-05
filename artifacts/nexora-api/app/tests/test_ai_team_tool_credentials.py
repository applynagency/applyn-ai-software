"""Tests for Sprint 39C — Real Tool Credentials & Connectors."""

import os

import pytest
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.tests.conftest import auth_headers, create_authenticated_user


async def _agent(client, token):
    team = (
        await client.post("/v1/ai-teams", headers=auth_headers(token), json={"name": "Ops"})
    ).json()
    agent = (
        await client.post(
            "/v1/ai-team-agents",
            headers=auth_headers(token),
            json={
                "team_id": team["id"],
                "name": "SRE",
                "role": "Operations",
                "instructions": "Investigate.",
                "model": "claude-sonnet",
                "temperature": 0.2,
                "max_tokens": 200,
                "is_active": True,
            },
        )
    ).json()
    return team, agent


async def _tool(client, token, provider="KUBERNETES", name="Tool"):
    return (
        await client.post(
            "/v1/ai-tools",
            headers=auth_headers(token),
            json={"provider": provider, "name": name},
        )
    ).json()


async def _credential(client, token, provider, secret, name="Cred"):
    resp = await client.post(
        "/v1/credentials",
        headers=auth_headers(token),
        json={"provider": provider, "name": name, "secret": secret},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _real_postgres_secret():
    """Resolve a usable, real PostgreSQL credential for the real-read tests.

    Prefers ``TEST_REAL_POSTGRES_URL`` (set when a real Postgres is reachable,
    e.g. the app's own database) and falls back to ``DATABASE_URL``. Returns
    ``None`` when no real Postgres is available (e.g. the SQLite test harness),
    so the connector tests can skip cleanly instead of failing.
    """
    raw = os.environ.get("TEST_REAL_POSTGRES_URL") or settings.DATABASE_URL
    url = make_url(raw)
    if not url.get_backend_name().startswith("postgres") or not url.username:
        return None
    return {
        "host": url.host or "localhost",
        "port": url.port or 5432,
        "username": url.username,
        "password": url.password or "",
        "database": url.database,
    }


async def test_attach_and_detach_credential(client):
    _, tokens = await create_authenticated_user(client, email="c1@example.com", username="cred1")
    token = tokens["access_token"]
    tool = await _tool(client, token, provider="KUBERNETES", name="Prod Cluster")
    cred = await _credential(client, token, "KUBERNETES", {"kubeconfig": "apiVersion: v1"}, "K8s Prod")

    attached = await client.post(
        f"/v1/ai-tools/{tool['id']}/credentials",
        headers=auth_headers(token),
        json={"credential_id": cred["id"]},
    )
    assert attached.status_code == 201, attached.text
    assert attached.json()["provider"] == "KUBERNETES"

    status = await client.get(
        f"/v1/ai-tools/{tool['id']}/connection-status", headers=auth_headers(token)
    )
    body = status.json()
    assert body["attached"] is True
    assert body["mode"] == "REAL"
    assert body["credential_name"] == "K8s Prod"

    detached = await client.delete(
        f"/v1/ai-tools/{tool['id']}/credentials/{cred['id']}", headers=auth_headers(token)
    )
    assert detached.status_code == 204
    status2 = await client.get(
        f"/v1/ai-tools/{tool['id']}/connection-status", headers=auth_headers(token)
    )
    assert status2.json()["attached"] is False
    assert status2.json()["mode"] == "SIMULATED"


async def test_attach_provider_mismatch_rejected(client):
    _, tokens = await create_authenticated_user(client, email="c2@example.com", username="cred2")
    token = tokens["access_token"]
    tool = await _tool(client, token, provider="KUBERNETES")
    cred = await _credential(
        client, token, "AWS", {"access_key": "AKIA", "secret_key": "x", "region": "us-east-1"}
    )
    resp = await client.post(
        f"/v1/ai-tools/{tool['id']}/credentials",
        headers=auth_headers(token),
        json={"credential_id": cred["id"]},
    )
    assert resp.status_code == 400


async def test_slack_is_simulated(client):
    _, tokens = await create_authenticated_user(client, email="c3@example.com", username="cred3")
    token = tokens["access_token"]
    tool = await _tool(client, token, provider="SLACK", name="Workspace")
    status = await client.get(
        f"/v1/ai-tools/{tool['id']}/connection-status", headers=auth_headers(token)
    )
    body = status.json()
    assert body["supports_real_connection"] is False
    assert body["mode"] == "SIMULATED"


async def test_verify_invalid_credentials_is_safe(client):
    _, tokens = await create_authenticated_user(client, email="c4@example.com", username="cred4")
    token = tokens["access_token"]
    tool = await _tool(client, token, provider="GITHUB", name="Repos")
    cred = await _credential(client, token, "GITHUB", {"token": "ghp_totally_invalid_secret"}, "GH")
    await client.post(
        f"/v1/ai-tools/{tool['id']}/credentials",
        headers=auth_headers(token),
        json={"credential_id": cred["id"]},
    )
    resp = await client.post(f"/v1/ai-tools/{tool['id']}/verify", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["connected"] is False
    assert body["provider"] == "GITHUB"
    # Customer-safe error; never echoes the token.
    assert "ghp_totally_invalid_secret" not in resp.text
    assert body["error"]


async def test_verify_requires_attached_credential(client):
    _, tokens = await create_authenticated_user(client, email="c5@example.com", username="cred5")
    token = tokens["access_token"]
    tool = await _tool(client, token, provider="KUBERNETES")
    resp = await client.post(f"/v1/ai-tools/{tool['id']}/verify", headers=auth_headers(token))
    assert resp.status_code == 400


async def test_real_postgres_read(client):
    """Successful REAL read against the live database via a customer credential."""
    pg = _real_postgres_secret()
    if pg is None:
        pytest.skip("No real PostgreSQL available (set TEST_REAL_POSTGRES_URL).")
    _, tokens = await create_authenticated_user(client, email="c6@example.com", username="cred6")
    token = tokens["access_token"]
    _, agent = await _agent(client, token)
    tool = await _tool(client, token, provider="POSTGRESQL", name="App DB")
    cred = await _credential(client, token, "POSTGRESQL", pg, "App DB Cred")
    await client.post(
        f"/v1/ai-tools/{tool['id']}/credentials",
        headers=auth_headers(token),
        json={"credential_id": cred["id"]},
    )
    await client.post(
        f"/v1/ai-team-agents/{agent['id']}/tools",
        headers=auth_headers(token),
        json={"tool_id": tool["id"]},
    )

    # Connection verifies against the real database.
    verify = await client.post(f"/v1/ai-tools/{tool['id']}/verify", headers=auth_headers(token))
    assert verify.status_code == 200, verify.text
    assert verify.json()["connected"] is True

    # A real SELECT executes against the database.
    run = await client.post(
        f"/v1/ai-tools/{tool['id']}/execute",
        headers=auth_headers(token),
        json={"agent_id": agent["id"], "action": "select_query", "payload": {"sql": "SELECT 1 AS n"}},
    )
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["status"] == "COMPLETED"
    assert "row" in (body["response_summary"] or "").lower()
    assert "simulated" not in (body["response_summary"] or "").lower()


async def test_real_execution_audits_secret_used(client):
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.audit import AuditLog
    from app.models.credential import SecretAccessAudit

    pg = _real_postgres_secret()
    if pg is None:
        pytest.skip("No real PostgreSQL available (set TEST_REAL_POSTGRES_URL).")
    _, tokens = await create_authenticated_user(client, email="c7@example.com", username="cred7")
    token = tokens["access_token"]
    _, agent = await _agent(client, token)
    tool = await _tool(client, token, provider="POSTGRESQL", name="App DB")
    cred = await _credential(client, token, "POSTGRESQL", pg, "DB")
    await client.post(
        f"/v1/ai-tools/{tool['id']}/credentials",
        headers=auth_headers(token),
        json={"credential_id": cred["id"]},
    )
    await client.post(
        f"/v1/ai-team-agents/{agent['id']}/tools",
        headers=auth_headers(token),
        json={"tool_id": tool["id"]},
    )
    await client.post(
        f"/v1/ai-tools/{tool['id']}/execute",
        headers=auth_headers(token),
        json={"agent_id": agent["id"], "action": "select_query", "payload": {"sql": "SELECT 1"}},
    )

    async with AsyncSessionLocal() as session:
        audit_actions = {
            r.action for r in (await session.execute(select(AuditLog))).scalars().all()
        }
        secret_events = {
            r.event for r in (await session.execute(select(SecretAccessAudit))).scalars().all()
        }
    assert "tool_credential_attached" in audit_actions
    assert "tool_executed" in audit_actions
    assert "SECRET_USED" in secret_events


async def test_no_secret_leakage_in_runs(client):
    _, tokens = await create_authenticated_user(client, email="c8@example.com", username="cred8")
    token = tokens["access_token"]
    _, agent = await _agent(client, token)
    tool = await _tool(client, token, provider="GITHUB", name="Repos")
    cred = await _credential(client, token, "GITHUB", {"token": "ghp_leak_check_secret"}, "GH")
    await client.post(
        f"/v1/ai-tools/{tool['id']}/credentials",
        headers=auth_headers(token),
        json={"credential_id": cred["id"]},
    )
    await client.post(
        f"/v1/ai-team-agents/{agent['id']}/tools",
        headers=auth_headers(token),
        json={"tool_id": tool["id"]},
    )
    # Real connector attempt with an invalid token -> failure, but no leakage.
    await client.post(
        f"/v1/ai-tools/{tool['id']}/execute",
        headers=auth_headers(token),
        json={"agent_id": agent["id"], "action": "list_repositories", "payload": {"token": "ghp_leak_check_secret"}},
    )
    runs = await client.get(f"/v1/ai-tools/{tool['id']}/runs", headers=auth_headers(token))
    assert "ghp_leak_check_secret" not in runs.text


async def test_credential_tenant_isolation(client):
    _, tokens_a = await create_authenticated_user(client, email="ca@example.com", username="ciaa")
    _, tokens_b = await create_authenticated_user(client, email="cb@example.com", username="cibb")
    token_a = tokens_a["access_token"]
    token_b = tokens_b["access_token"]
    tool = await _tool(client, token_a, provider="KUBERNETES")
    cred = await _credential(client, token_a, "KUBERNETES", {"kubeconfig": "apiVersion: v1"})

    # Cross-org cannot see connection-status, attach, or verify the tool.
    assert (
        await client.get(
            f"/v1/ai-tools/{tool['id']}/connection-status", headers=auth_headers(token_b)
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/v1/ai-tools/{tool['id']}/credentials",
            headers=auth_headers(token_b),
            json={"credential_id": cred["id"]},
        )
    ).status_code == 404
    assert (
        await client.post(f"/v1/ai-tools/{tool['id']}/verify", headers=auth_headers(token_b))
    ).status_code == 404
