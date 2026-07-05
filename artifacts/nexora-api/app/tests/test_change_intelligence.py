"""Tests for Sprint 40C — Deployment Change Intelligence."""

from datetime import UTC, datetime, timedelta

from app.services import change_intelligence
from app.tests.conftest import auth_headers, create_authenticated_user


async def _team_agent(client, token, name="Ops"):
    team = (
        await client.post("/v1/ai-teams", headers=auth_headers(token), json={"name": name})
    ).json()
    agent = (
        await client.post(
            "/v1/ai-team-agents",
            headers=auth_headers(token),
            json={
                "team_id": team["id"],
                "name": "SRE",
                "role": "Operations",
                "instructions": "Investigate production incidents.",
                "model": "claude-sonnet",
                "temperature": 0.2,
                "max_tokens": 300,
                "is_active": True,
            },
        )
    ).json()
    return team, agent


async def _tool(client, token, provider, name=None):
    return (
        await client.post(
            "/v1/ai-tools",
            headers=auth_headers(token),
            json={"provider": provider, "name": name or f"{provider} tool"},
        )
    ).json()


async def _assign(client, token, agent_id, tool_id):
    resp = await client.post(
        f"/v1/ai-team-agents/{agent_id}/tools",
        headers=auth_headers(token),
        json={"tool_id": tool_id},
    )
    assert resp.status_code in (200, 201), resp.text


async def _investigate(client, token, providers, prompt="Production incident."):
    team, agent = await _team_agent(client, token)
    for provider in providers:
        tool = await _tool(client, token, provider)
        await _assign(client, token, agent["id"], tool["id"])
    inv = (
        await client.post(
            "/v1/incidents/investigate",
            headers=auth_headers(token),
            json={"team_id": team["id"], "prompt": prompt},
        )
    ).json()
    return team, agent, inv


# ----------------------------------------------------------- unit
def test_build_changes_sorted_with_actor_and_version():
    base = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    changes = change_intelligence.build_changes(["GITHUB", "KUBERNETES"], base)
    ts = [c["change_timestamp"] for c in changes]
    assert ts == sorted(ts)
    gh_deploy = [c for c in changes if c["provider"] == "GITHUB" and c["change_type"] == "deployment"]
    assert gh_deploy and gh_deploy[0]["version"] == "v2.8.4"
    assert gh_deploy[0]["actor"] == "john.doe"


def test_correlate_picks_github_deployment_over_k8s_rollout():
    base = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    # First failure 4 minutes after the deployment (mirrors 40B timeline).
    failure_at = base + timedelta(minutes=4)
    changes = change_intelligence.build_changes(
        ["GITHUB", "KUBERNETES", "AWS", "AZURE"], base
    )
    result = change_intelligence.correlate_changes(changes, failure_at)
    sc = result["suspected_change"]
    assert sc is not None
    # The originating GitHub deployment wins over the downstream K8s rollout.
    assert sc["provider"] == "GITHUB"
    assert sc["change_type"] == "deployment"
    assert sc["version"] == "v2.8.4"
    assert sc["actor"] == "john.doe"
    assert sc["commit"] == "8d2f91"
    assert sc["minutes_to_failure"] == 4
    assert sc["confidence_score"] >= 80
    # GitHub summary surfaces latest commit/merge/release.
    assert result["latest_commit"] == "8d2f91"
    assert result["latest_release"] == "v2.8.4"
    assert result["latest_merge"] == "#481"


def test_correlate_no_changes():
    result = change_intelligence.correlate_changes([], None)
    assert result["suspected_change"] is None
    assert result["confidence_score"] == 10


# ----------------------------------------------------------- API
async def test_changes_api_collection_and_correlation(client):
    _, tokens = await create_authenticated_user(client, email="ch1@example.com", username="ch1")
    token = tokens["access_token"]
    _, _, inv = await _investigate(client, token, ["GITHUB", "KUBERNETES", "PROMETHEUS", "DATADOG"])

    resp = await client.get(f"/v1/incidents/{inv['id']}/changes", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["changes"]) >= 5
    # Each change carries what/when/who/version.
    for c in data["changes"]:
        assert c["provider"] and c["change_type"] and c["change_timestamp"] and c["title"]
    sc = data["suspected_change"]
    assert sc is not None
    assert sc["provider"] == "GITHUB"
    assert sc["version"] == "v2.8.4"
    assert sc["actor"] == "john.doe"
    assert sc["commit"] == "8d2f91"
    assert data["confidence_score"] == sc["confidence_score"]
    assert 0 <= data["confidence_score"] <= 100
    assert data["latest_release"] == "v2.8.4"


async def test_changes_version_and_commit_tracking(client):
    _, tokens = await create_authenticated_user(client, email="ch2@example.com", username="ch2")
    token = tokens["access_token"]
    _, _, inv = await _investigate(client, token, ["GITHUB"])
    data = (
        await client.get(f"/v1/incidents/{inv['id']}/changes", headers=auth_headers(token))
    ).json()
    versions = {c["version"] for c in data["changes"]}
    assert "v2.8.4" in versions
    assert "8d2f91" in versions  # commit SHA tracked as a change version


async def test_changes_tenant_isolation(client):
    _, tokens_a = await create_authenticated_user(client, email="cha@example.com", username="chaa")
    _, tokens_b = await create_authenticated_user(client, email="chb@example.com", username="chbb")
    token_a = tokens_a["access_token"]
    token_b = tokens_b["access_token"]
    _, _, inv = await _investigate(client, token_a, ["GITHUB", "KUBERNETES"])
    resp = await client.get(
        f"/v1/incidents/{inv['id']}/changes", headers=auth_headers(token_b)
    )
    assert resp.status_code == 404


async def test_changes_no_secret_leakage(client):
    _, tokens = await create_authenticated_user(client, email="ch3@example.com", username="ch3")
    token = tokens["access_token"]
    _, _, inv = await _investigate(client, token, ["GITHUB", "KUBERNETES", "AWS"])
    resp = await client.get(f"/v1/incidents/{inv['id']}/changes", headers=auth_headers(token))
    raw = resp.text.lower()
    for needle in ("password", "secret", "token", "access_key", "private_key"):
        assert needle not in raw


async def test_changes_audit_logging(client):
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.audit import AuditLog

    _, tokens = await create_authenticated_user(client, email="ch4@example.com", username="ch4")
    token = tokens["access_token"]
    _, _, inv = await _investigate(client, token, ["GITHUB", "KUBERNETES"])

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(AuditLog))).scalars().all()
    completed = [r for r in rows if r.action == "incident_investigation_completed"]
    assert completed
    assert any((r.details or {}).get("change_events", 0) >= 1 for r in completed)
