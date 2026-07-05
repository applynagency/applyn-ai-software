"""Tests for Sprint 40B — Alert Correlation & Incident Timeline Engine."""

from datetime import UTC, datetime

from app.services import incident_correlation
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


async def _investigate_multi(client, token, providers, prompt="Production incident."):
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


# ----------------------------------------------------------- unit: correlation
def test_correlation_unit_change_before_failure():
    base = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    events = incident_correlation.build_events(
        ["GITHUB", "KUBERNETES", "PROMETHEUS", "DATADOG"], base
    )
    # Sorted ascending by timestamp.
    ts = [e["event_timestamp"] for e in events]
    assert ts == sorted(ts)

    analysis = incident_correlation.correlate(events)
    assert 0 <= analysis["confidence_score"] <= 100
    assert analysis["confidence_score"] >= 70  # tight change->failure correlation
    # Earliest change is the GitHub deployment.
    assert analysis["suspected_provider"] == "GITHUB"
    assert "deployment" in analysis["suspected_trigger"].lower()
    assert analysis["minutes_between_change_and_failure"] is not None
    assert analysis["minutes_between_change_and_failure"] >= 0
    assert "KUBERNETES" in analysis["impacted_systems"]


def test_correlation_unit_no_change_low_confidence():
    base = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    # Prometheus alone produces degradation/failure but no "change" event.
    events = incident_correlation.build_events(["PROMETHEUS"], base)
    analysis = incident_correlation.correlate(events)
    assert analysis["suspected_trigger"] is None
    assert analysis["confidence_score"] <= 30


def test_correlation_unit_empty():
    analysis = incident_correlation.correlate([])
    assert analysis["confidence_score"] == 10
    assert analysis["suspected_trigger"] is None
    assert analysis["impacted_systems"] == []


# ----------------------------------------------------------- API: persistence
async def test_timeline_persisted_and_ordered(client):
    _, tokens = await create_authenticated_user(client, email="tl1@example.com", username="tl1")
    token = tokens["access_token"]
    _, _, inv = await _investigate_multi(
        client, token, ["GITHUB", "KUBERNETES", "PROMETHEUS", "DATADOG"]
    )

    tl = await client.get(f"/v1/incidents/{inv['id']}/timeline", headers=auth_headers(token))
    assert tl.status_code == 200
    data = tl.json()
    timeline = data["timeline"]
    assert len(timeline) >= 4
    # Events sorted ascending by timestamp.
    stamps = [e["event_timestamp"] for e in timeline]
    assert stamps == sorted(stamps)
    # Each event carries the required normalized fields.
    for e in timeline:
        assert e["provider"]
        assert e["event_type"]
        assert e["severity"] in ("INFO", "WARNING", "CRITICAL")
        assert e["title"]


async def test_change_correlation_and_confidence(client):
    _, tokens = await create_authenticated_user(client, email="tl2@example.com", username="tl2")
    token = tokens["access_token"]
    _, _, inv = await _investigate_multi(
        client, token, ["GITHUB", "KUBERNETES", "PROMETHEUS", "DATADOG"]
    )

    tl = (
        await client.get(f"/v1/incidents/{inv['id']}/timeline", headers=auth_headers(token))
    ).json()
    ta = tl["trigger_analysis"]
    assert ta is not None
    assert tl["confidence_score"] == ta["confidence_score"]
    assert 0 <= tl["confidence_score"] <= 100
    assert ta["suspected_provider"] == "GITHUB"
    assert ta["minutes_between_change_and_failure"] is not None


async def test_rca_includes_new_sections(client):
    _, tokens = await create_authenticated_user(client, email="tl3@example.com", username="tl3")
    token = tokens["access_token"]
    _, _, inv = await _investigate_multi(client, token, ["GITHUB", "KUBERNETES", "PROMETHEUS"])

    detail = (
        await client.get(f"/v1/incidents/{inv['id']}", headers=auth_headers(token))
    ).json()
    summary = detail["summary"]
    assert "### Timeline" in summary
    assert "### Trigger Analysis" in summary
    assert "### Impact Analysis" in summary
    assert "### Confidence Score" in summary
    # Correlation fields persisted on the investigation.
    assert detail["confidence_score"] is not None
    assert detail["suspected_provider"] == "GITHUB"


async def test_timeline_tenant_isolation(client):
    _, tokens_a = await create_authenticated_user(client, email="tla@example.com", username="tlaa")
    _, tokens_b = await create_authenticated_user(client, email="tlb@example.com", username="tlbb")
    token_a = tokens_a["access_token"]
    token_b = tokens_b["access_token"]
    _, _, inv = await _investigate_multi(client, token_a, ["GITHUB", "KUBERNETES"])

    resp = await client.get(
        f"/v1/incidents/{inv['id']}/timeline", headers=auth_headers(token_b)
    )
    assert resp.status_code == 404


async def test_timeline_no_secret_leakage(client):
    _, tokens = await create_authenticated_user(client, email="tl4@example.com", username="tl4")
    token = tokens["access_token"]
    _, _, inv = await _investigate_multi(
        client, token, ["GITHUB", "KUBERNETES", "DATADOG"]
    )
    tl = await client.get(f"/v1/incidents/{inv['id']}/timeline", headers=auth_headers(token))
    raw = tl.text.lower()
    for needle in ("password", "secret", "token", "access_key", "private"):
        assert needle not in raw


async def test_timeline_audit_logging(client):
    from sqlalchemy import select

    from app.database.session import AsyncSessionLocal
    from app.models.audit import AuditLog

    _, tokens = await create_authenticated_user(client, email="tl5@example.com", username="tl5")
    token = tokens["access_token"]
    _, _, inv = await _investigate_multi(client, token, ["GITHUB", "KUBERNETES"])

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(AuditLog))).scalars().all()
    completed = [r for r in rows if r.action == "incident_investigation_completed"]
    assert completed
    # Correlation telemetry is audited (no secrets, just counts/score).
    assert any(
        (r.details or {}).get("timeline_events", 0) >= 1 for r in completed
    )
