"""Tests for Sprint 41A — Remediation Recommendation Engine (recommendation-only)."""

from app.services import remediation_recommendations as rr
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
def test_engine_recommends_rollback_for_deployment_then_failure():
    change_analysis = {
        "suspected_change": {
            "provider": "GITHUB",
            "change_type": "deployment",
            "version": "v2.8.4",
            "reason": "Failure started 4 minutes after the deployment.",
        },
        "confidence_score": 91,
    }
    events = [
        {"event_type": "crashloop"},
        {"event_type": "error_spike"},
        {"event_type": "latency_spike"},
    ]
    recs = rr.generate(timeline_events=events, change_analysis=change_analysis, timeline_confidence=91)
    assert recs
    # Ranked: order is 1..n contiguous.
    assert [r["recommendation_order"] for r in recs] == list(range(1, len(recs) + 1))
    # Sorted by confidence descending.
    confs = [r["confidence_score"] for r in recs]
    assert confs == sorted(confs, reverse=True)
    top = recs[0]
    assert "rollback" in top["title"].lower()
    assert top["recommendation_type"] == "Deployment"
    assert top["risk_level"] == "HIGH"
    assert top["confidence_score"] == 94  # change_conf 91 + 3
    assert top["estimated_recovery_minutes"] == 15
    # Risk levels are all valid; recovery snaps to supported buckets.
    for r in recs:
        assert r["risk_level"] in ("LOW", "MEDIUM", "HIGH")
        assert r["estimated_recovery_minutes"] in (5, 15, 30, 60)
        assert 5 <= r["confidence_score"] <= 99


def test_engine_signal_specific_rules():
    recs = rr.generate(
        timeline_events=[{"event_type": "memory_spike"}, {"event_type": "cpu_spike"}],
        change_analysis={"suspected_change": None, "confidence_score": 0},
        timeline_confidence=60,
    )
    titles = " | ".join(r["title"].lower() for r in recs)
    assert "memory" in titles
    assert "replica" in titles or "scale" in titles


def test_engine_fallback_when_no_signals():
    recs = rr.generate(timeline_events=[], change_analysis=None, timeline_confidence=None)
    assert len(recs) == 1
    assert recs[0]["recommendation_type"] == "Monitoring"


# ----------------------------------------------------------- API
async def test_recommendations_api(client):
    _, tokens = await create_authenticated_user(client, email="r1@example.com", username="rec1")
    token = tokens["access_token"]
    _, _, inv = await _investigate(client, token, ["GITHUB", "KUBERNETES", "PROMETHEUS", "DATADOG"])

    resp = await client.get(
        f"/v1/incidents/{inv['id']}/recommendations", headers=auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    recs = resp.json()["recommendations"]
    assert len(recs) >= 3
    # Ranked + every field present.
    assert [r["recommendation_order"] for r in recs] == list(range(1, len(recs) + 1))
    for r in recs:
        assert r["recommendation_type"]
        assert r["risk_level"] in ("LOW", "MEDIUM", "HIGH")
        assert 0 <= r["confidence_score"] <= 100
        assert r["estimated_recovery_minutes"] in (5, 15, 30, 60)
    # A rollback recommendation leads when a deployment is suspected.
    assert any("rollback" in r["title"].lower() for r in recs)
    assert recs[0]["risk_level"] == "HIGH"


async def test_recommendations_tenant_isolation(client):
    _, tokens_a = await create_authenticated_user(client, email="ra@example.com", username="recaa")
    _, tokens_b = await create_authenticated_user(client, email="rb@example.com", username="recbb")
    token_a = tokens_a["access_token"]
    token_b = tokens_b["access_token"]
    _, _, inv = await _investigate(client, token_a, ["GITHUB", "KUBERNETES"])
    resp = await client.get(
        f"/v1/incidents/{inv['id']}/recommendations", headers=auth_headers(token_b)
    )
    assert resp.status_code == 404


async def test_recommendations_no_secret_leakage(client):
    _, tokens = await create_authenticated_user(client, email="r2@example.com", username="rec2")
    token = tokens["access_token"]
    _, _, inv = await _investigate(client, token, ["GITHUB", "KUBERNETES", "AWS"])
    resp = await client.get(
        f"/v1/incidents/{inv['id']}/recommendations", headers=auth_headers(token)
    )
    raw = resp.text.lower()
    for needle in ("password", "secret", "token", "access_key", "private_key"):
        assert needle not in raw


async def test_recommendations_audit_logging(client):
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.audit import AuditLog

    _, tokens = await create_authenticated_user(client, email="r3@example.com", username="rec3")
    token = tokens["access_token"]
    _, _, inv = await _investigate(client, token, ["GITHUB", "KUBERNETES"])

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(AuditLog))).scalars().all()
    completed = [r for r in rows if r.action == "incident_investigation_completed"]
    assert completed
    assert any((r.details or {}).get("recommendations", 0) >= 1 for r in completed)
