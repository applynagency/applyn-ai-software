"""Sprint 54B.1 — Pilot Journey Gap Remediation tests.

Validates the four journey-breaking fixes identified in Sprint 54B:

  1. Creating an organization auto-switches context + issues an org-scoped token
     (no manual ``/switch`` required → no post-create 403 dead-end).
  2. Onboarding completion auto-provisions the default "SRE Team" with an
     Incident Investigator + RCA agent, marked as default.
  3. ``team_id`` is optional on incident investigation and defaults to the org's
     default team (no hidden 422 prerequisite).
  4. A sample incident can be generated via the existing demo scenario engine.
"""

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.ai_team import AITeam, AITeamAgent
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers
# The infrastructure wizard was folded into the single onboarding experience.
ONB = "/v1/onboarding"


async def _new_user(client, n: str):
    me, tokens = await create_authenticated_user(
        client, email=f"pr{n}@e.com", username=f"pr{n}"
    )
    return me, tokens["access_token"]


async def _drive_and_complete_wizard(client, token, providers=None):
    r = await client.post(f"{ONB}/start", headers=H(token),
                          json={"organization_name": "Acme"})
    assert r.status_code == 201, r.text
    wid = r.json()["id"]
    r = await client.post(f"{ONB}/{wid}/complete", headers=H(token))
    assert r.status_code == 200, r.text
    return wid, r.json()


# ----------------------------------------------------------------------- #
# Fix 1 — organization context auto-switch
# ----------------------------------------------------------------------- #
async def test_create_org_auto_switches_and_issues_org_token(client):
    _, token = await _new_user(client, "ctx")
    r = await client.post("/v1/organizations", headers=H(token),
                          json={"name": "Acme Inc"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["auto_switched"] is True
    ctx = body["context"]
    assert ctx is not None
    assert ctx["access_token"]
    assert ctx["refresh_token"]
    assert ctx["organization_id"] == body["id"]
    assert ctx["role"] == "OWNER"

    # The returned org-scoped token works immediately — no manual /switch.
    org_token = ctx["access_token"]
    started = await client.post(f"{ONB}/start", headers=H(org_token), json={})
    assert started.status_code == 201, started.text


# ----------------------------------------------------------------------- #
# Fix 2 — default AI team on onboarding completion
# ----------------------------------------------------------------------- #
async def test_complete_provisions_default_team(client):
    me, token = await _new_user(client, "team")
    _, final = await _drive_and_complete_wizard(client, token)

    dt = final["default_team"]
    assert dt is not None
    assert dt["name"] == "SRE Team"
    assert dt["is_default"] is True
    assert dt["created"] is True
    assert set(dt["agents"]) == {"Incident Investigator", "RCA Agent"}

    keys = {a["key"] for a in final["next_actions"]}
    assert "generate_sample_incident" in keys

    org_id = me["organization_id"] if "organization_id" in me else None
    async with AsyncSessionLocal() as session:
        team = (await session.execute(
            select(AITeam).where(AITeam.is_default.is_(True))
        )).scalars().all()
        assert any(t.name == "SRE Team" for t in team)
        target = next(t for t in team if t.name == "SRE Team")
        if org_id:
            assert target.organization_id == org_id
        agents = (await session.execute(
            select(AITeamAgent).where(AITeamAgent.team_id == target.id)
        )).scalars().all()
        assert {a.role for a in agents} == {"Incident Investigator", "Root Cause Analyst"}


async def test_complete_is_idempotent_for_default_team(client):
    _, token = await _new_user(client, "idem")
    wid, _ = await _drive_and_complete_wizard(client, token)
    # Completing again must not create a second default team.
    r = await client.post(f"{ONB}/{wid}/complete", headers=H(token))
    assert r.status_code == 200, r.text
    assert r.json()["default_team"]["created"] is False
    async with AsyncSessionLocal() as session:
        defaults = (await session.execute(
            select(AITeam).where(AITeam.is_default.is_(True))
        )).scalars().all()
        assert len([t for t in defaults if t.name == "SRE Team"]) == 1


# ----------------------------------------------------------------------- #
# Fix 3 — investigation defaults to the org default team
# ----------------------------------------------------------------------- #
async def test_investigate_without_team_id_uses_default_team(client):
    _, token = await _new_user(client, "inv")
    _, final = await _drive_and_complete_wizard(client, token)
    default_team_id = final["default_team"]["id"]

    r = await client.post("/v1/incidents/investigate", headers=H(token),
                          json={"prompt": "Checkout latency spiked after the 14:00 deploy"})
    assert r.status_code == 201, r.text
    assert r.json()["team_id"] == default_team_id


async def test_investigate_without_team_and_no_default_is_clear_400(client):
    _, token = await _new_user(client, "nodef")
    r = await client.post("/v1/incidents/investigate", headers=H(token),
                          json={"prompt": "Something is broken"})
    assert r.status_code == 400, r.text
    assert "default team" in r.json()["detail"].lower()


# ----------------------------------------------------------------------- #
# Fix 4 — generate sample incident via the demo scenario engine
# ----------------------------------------------------------------------- #
async def test_generate_sample_incident(client):
    _, token = await _new_user(client, "sample")
    wid, _ = await _drive_and_complete_wizard(client, token)

    r = await client.post(f"{ONB}/{wid}/sample-incident", headers=H(token))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["scenario"] == "CHECKOUT_OUTAGE"
    assert body["incident_id"]

    listing = await client.get("/v1/incidents", headers=H(token))
    assert listing.status_code == 200, listing.text
    ids = {i["id"] for i in listing.json()["items"]}
    assert body["incident_id"] in ids
