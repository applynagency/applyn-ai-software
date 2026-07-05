"""Tests for Sprint 46D - AI Incident War Room.

Covers room creation (with/without incident), the multi-agent discussion
(findings from all six agents, challenges, ranked hypotheses, remediation
proposals, CTO consensus), consensus RCA + remediation plan generation,
mandatory-human-approval / no-autonomous-execution invariants, re-run guard,
list/get/404, tenant isolation, and audit logging. Read-only.
"""

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers


async def _team_agent(client, token):
    team = (await client.post("/v1/ai-teams", headers=H(token), json={"name": "Ops"})).json()
    await client.post("/v1/ai-team-agents", headers=H(token),
                      json={"team_id": team["id"], "name": "SRE", "role": "Ops", "instructions": "x",
                            "model": "claude-sonnet", "temperature": 0.2, "max_tokens": 300, "is_active": True})


async def _incident(client, token, name="HighErrorRate", service="checkout"):
    await _team_agent(client, token)
    body = (await client.post("/v1/monitoring/poll", headers=H(token),
            json={"alerts": [{"provider": "PROMETHEUS", "alert_id": f"a-{name}", "alert_name": name,
                              "severity": "CRITICAL", "service": service, "environment": "production"}]})).json()
    return body["alerts"][0]["incident_id"]


async def _create(client, token, incident_id=None, title=None):
    return await client.post("/v1/war-rooms", headers=H(token),
                             json={"incident_id": incident_id, "title": title})


# ============================== creation ================================= #
async def test_create_war_room_with_incident(client):
    _, t = await create_authenticated_user(client, email="wr1@e.com", username="wr1")
    token = t["access_token"]
    iid = await _incident(client, token)
    r = await _create(client, token, iid)
    assert r.status_code == 201, r.text
    room = r.json()
    assert room["status"] == "OPEN"
    assert room["incident_id"] == iid
    assert room["requires_approval"] is True
    assert room["autonomous_execution"] is False
    assert len(room["messages"]) == 1  # system opener
    assert room["messages"][0]["agent"] == "SYSTEM"


async def test_create_without_incident(client):
    _, t = await create_authenticated_user(client, email="wr2@e.com", username="wr2")
    token = t["access_token"]
    r = await _create(client, token, None, "Ad-hoc Room")
    assert r.status_code == 201
    assert r.json()["title"] == "Ad-hoc Room"


async def test_create_unknown_incident_404(client):
    _, t = await create_authenticated_user(client, email="wr3@e.com", username="wr3")
    token = t["access_token"]
    assert (await _create(client, token, "nope")).status_code == 404


# ============================== execution ================================ #
async def test_execute_multi_agent_consensus(client):
    _, t = await create_authenticated_user(client, email="wr4@e.com", username="wr4")
    token = t["access_token"]
    iid = await _incident(client, token, name="CrashLoopBackOff on checkout pod")
    room = (await _create(client, token, iid)).json()
    r = await client.post(f"/v1/war-rooms/{room['id']}/execute", headers=H(token))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "AWAITING_APPROVAL"
    assert out["requires_approval"] is True
    assert out["autonomous_execution"] is False
    # all six specialist agents participated
    assert set(out["participating_agents"]) == {"CTO", "SRE", "KUBERNETES", "GITHUB", "DATABASE", "SECURITY"}
    types = {m["message_type"] for m in out["messages"]}
    assert {"FINDING", "CHALLENGE", "HYPOTHESIS", "REMEDIATION", "CONSENSUS"} <= types
    # consensus RCA + remediation plan present
    assert out["consensus_rca"] and "Primary Root Cause" in out["consensus_rca"]
    assert out["remediation_plan"]
    assert all(s["requires_approval"] for s in out["remediation_plan"])
    assert 0 <= out["confidence_score"] <= 100
    # kubernetes signal should surface a k8s hypothesis
    hyp_text = " ".join(m["content"].lower() for m in out["messages"] if m["message_type"] == "HYPOTHESIS")
    assert "kubernetes" in hyp_text or "crashloop" in hyp_text


async def test_execute_is_single_shot(client):
    _, t = await create_authenticated_user(client, email="wr5@e.com", username="wr5")
    token = t["access_token"]
    room = (await _create(client, token)).json()
    assert (await client.post(f"/v1/war-rooms/{room['id']}/execute", headers=H(token))).status_code == 200
    # second execute is rejected (already convened)
    assert (await client.post(f"/v1/war-rooms/{room['id']}/execute", headers=H(token))).status_code == 400


async def test_execute_unknown_404(client):
    _, t = await create_authenticated_user(client, email="wr6@e.com", username="wr6")
    token = t["access_token"]
    assert (await client.post("/v1/war-rooms/nope/execute", headers=H(token))).status_code == 404


# ============================== list / get =============================== #
async def test_list_and_get(client):
    _, t = await create_authenticated_user(client, email="wr7@e.com", username="wr7")
    token = t["access_token"]
    room = (await _create(client, token)).json()
    await client.post(f"/v1/war-rooms/{room['id']}/execute", headers=H(token))
    lst = (await client.get("/v1/war-rooms", headers=H(token))).json()
    assert len(lst) == 1 and lst[0]["id"] == room["id"]
    got = (await client.get(f"/v1/war-rooms/{room['id']}", headers=H(token))).json()
    assert got["id"] == room["id"] and got["status"] == "AWAITING_APPROVAL"
    assert len(got["messages"]) > 5
    assert (await client.get("/v1/war-rooms/nope", headers=H(token))).status_code == 404


# ============================== isolation ================================ #
async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="wrA@e.com", username="wrA")
    _, t2 = await create_authenticated_user(client, email="wrB@e.com", username="wrB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    room = (await _create(client, tok1)).json()
    assert (await client.get("/v1/war-rooms", headers=H(tok2))).json() == []
    assert (await client.get(f"/v1/war-rooms/{room['id']}", headers=H(tok2))).status_code == 404
    assert (await client.post(f"/v1/war-rooms/{room['id']}/execute", headers=H(tok2))).status_code == 404


# ============================== audit ==================================== #
async def test_audit_logging(client):
    me, t = await create_authenticated_user(client, email="wr8@e.com", username="wr8")
    token = t["access_token"]
    room = (await _create(client, token)).json()
    await client.post(f"/v1/war-rooms/{room['id']}/execute", headers=H(token))
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert {"war_room_created", "war_room_executed"} <= actions
