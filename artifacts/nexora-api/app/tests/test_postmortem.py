"""Tests for Sprint 44A — AI Postmortem & Learning Engine.

Covers manual generation from an incident, regeneration (versioning), auto
generation when an incident is resolved (on-call RESOLVED state), idempotency,
list/get, PDF/HTML/Markdown export, tenant isolation, audit logging, and
no-secret-leakage. Generating a postmortem never mutates the incident workflow.
"""

import json

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.postmortem import IncidentPostmortem
from app.tests.conftest import auth_headers, create_authenticated_user


async def _team_agent(client, token, name="Ops"):
    team = (await client.post("/v1/ai-teams", headers=auth_headers(token), json={"name": name})).json()
    await client.post(
        "/v1/ai-team-agents",
        headers=auth_headers(token),
        json={"team_id": team["id"], "name": "SRE", "role": "Ops", "instructions": "x",
              "model": "claude-sonnet", "temperature": 0.2, "max_tokens": 300, "is_active": True},
    )
    return team


def _alert(**over):
    base = {"provider": "PROMETHEUS", "alert_id": "a1", "alert_name": "HighErrorRate",
            "severity": "CRITICAL", "service": "checkout", "environment": "production"}
    base.update(over)
    return base


async def _incident(client, token):
    """Create a monitoring-driven incident (full investigation + assignment)."""
    await _team_agent(client, token)
    body = (await client.post("/v1/monitoring/poll", headers=auth_headers(token),
                              json={"alerts": [_alert()]})).json()
    return body["alerts"][0]["incident_id"]


async def _generate(client, token, incident_id, force=True):
    return await client.post(
        f"/v1/incidents/{incident_id}/generate-postmortem",
        headers=auth_headers(token), json={"force": force},
    )


# ============================== generation ================================= #
async def test_generate_postmortem(client):
    _, tokens = await create_authenticated_user(client, email="pm1@e.com", username="pmu1")
    token = tokens["access_token"]
    incident_id = await _incident(client, token)
    assert incident_id

    r = await _generate(client, token, incident_id)
    assert r.status_code == 201, r.text
    pm = r.json()
    assert pm["investigation_id"] == incident_id
    assert pm["status"] == "GENERATED"
    assert pm["version"] == 1
    assert pm["generated_by"] == "MANUAL"
    # All required executive sections present.
    for section in ("executive_summary", "impact_analysis", "timeline_summary",
                    "root_cause", "triggering_change", "resolution", "lessons_learned"):
        assert pm[section], f"missing {section}"
    assert len(pm["action_items"]) >= 1
    assert "## Executive Summary" in pm["content_markdown"]
    assert "## Root Cause" in pm["content_markdown"]


async def test_generate_unknown_incident_404(client):
    _, tokens = await create_authenticated_user(client, email="pm2@e.com", username="pmu2")
    token = tokens["access_token"]
    r = await _generate(client, token, "does-not-exist")
    assert r.status_code == 404


# ============================== regeneration =============================== #
async def test_regeneration_increments_version(client):
    _, tokens = await create_authenticated_user(client, email="pm3@e.com", username="pmu3")
    token = tokens["access_token"]
    incident_id = await _incident(client, token)
    first = (await _generate(client, token, incident_id)).json()
    assert first["version"] == 1 and first["status"] == "GENERATED"
    second = (await _generate(client, token, incident_id, force=True)).json()
    assert second["id"] == first["id"]
    assert second["version"] == 2
    assert second["status"] == "REGENERATED"


# ============================== list / get ================================= #
async def test_list_and_get(client):
    _, tokens = await create_authenticated_user(client, email="pm4@e.com", username="pmu4")
    token = tokens["access_token"]
    incident_id = await _incident(client, token)
    pm = (await _generate(client, token, incident_id)).json()

    lst = (await client.get("/v1/postmortems", headers=auth_headers(token))).json()
    assert lst["total"] >= 1
    assert any(i["id"] == pm["id"] for i in lst["items"])

    one = await client.get(f"/v1/postmortems/{pm['id']}", headers=auth_headers(token))
    assert one.status_code == 200 and one.json()["id"] == pm["id"]

    assert (await client.get("/v1/postmortems/nope", headers=auth_headers(token))).status_code == 404


# ============================== export ===================================== #
async def test_export_pdf_html_markdown(client):
    _, tokens = await create_authenticated_user(client, email="pm5@e.com", username="pmu5")
    token = tokens["access_token"]
    incident_id = await _incident(client, token)
    pm = (await _generate(client, token, incident_id)).json()

    pdf = await client.get(f"/v1/postmortems/{pm['id']}/export?format=pdf", headers=auth_headers(token))
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content[:5] == b"%PDF-"
    assert b"%%EOF" in pdf.content
    assert "attachment" in pdf.headers.get("content-disposition", "")

    md = await client.get(f"/v1/postmortems/{pm['id']}/export?format=markdown", headers=auth_headers(token))
    assert md.status_code == 200 and md.text.startswith("# Postmortem")

    htm = await client.get(f"/v1/postmortems/{pm['id']}/export?format=html", headers=auth_headers(token))
    assert htm.status_code == 200 and "<h1>" in htm.text

    bad = await client.get(f"/v1/postmortems/{pm['id']}/export?format=xls", headers=auth_headers(token))
    assert bad.status_code == 400


# ============================== auto generation ============================ #
async def test_auto_generate_on_resolve(client):
    _, tokens = await create_authenticated_user(client, email="pm6@e.com", username="pmu6")
    token = tokens["access_token"]
    incident_id = await _incident(client, token)

    # No postmortem yet.
    assert (await client.get("/v1/postmortems", headers=auth_headers(token))).json()["total"] == 0

    res = await client.post(f"/v1/oncall/incidents/{incident_id}/state",
                            headers=auth_headers(token), json={"state": "RESOLVED"})
    assert res.status_code == 200 and res.json()["resolved_at"] is not None

    lst = (await client.get("/v1/postmortems", headers=auth_headers(token))).json()
    assert lst["total"] == 1
    pm = lst["items"][0]
    assert pm["investigation_id"] == incident_id
    assert pm["generated_by"] == "AUTO"


async def test_auto_generate_is_idempotent(client):
    _, tokens = await create_authenticated_user(client, email="pm7@e.com", username="pmu7")
    token = tokens["access_token"]
    incident_id = await _incident(client, token)
    for _ in range(3):
        await client.post(f"/v1/oncall/incidents/{incident_id}/state",
                          headers=auth_headers(token), json={"state": "RESOLVED"})
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(IncidentPostmortem).where(IncidentPostmortem.investigation_id == incident_id)
        )).scalars().all()
    assert len(rows) == 1
    assert rows[0].version == 1  # not bumped by repeated resolves


async def test_resolve_then_manual_regenerate(client):
    _, tokens = await create_authenticated_user(client, email="pm8@e.com", username="pmu8")
    token = tokens["access_token"]
    incident_id = await _incident(client, token)
    await client.post(f"/v1/oncall/incidents/{incident_id}/state",
                      headers=auth_headers(token), json={"state": "RESOLVED"})
    # Manual regeneration after the auto one.
    r = await _generate(client, token, incident_id, force=True)
    assert r.status_code == 201
    assert r.json()["version"] == 2
    assert r.json()["generated_by"] == "MANUAL"


# ============================== isolation ================================== #
async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="pmA@e.com", username="pmuA")
    _, t2 = await create_authenticated_user(client, email="pmB@e.com", username="pmuB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    incident_id = await _incident(client, tok1)
    pm = (await _generate(client, tok1, incident_id)).json()

    lst = (await client.get("/v1/postmortems", headers=auth_headers(tok2))).json()
    assert lst["total"] == 0
    assert (await client.get(f"/v1/postmortems/{pm['id']}", headers=auth_headers(tok2))).status_code == 404
    assert (await client.get(f"/v1/postmortems/{pm['id']}/export", headers=auth_headers(tok2))).status_code == 404
    # org B cannot generate on org A's incident
    assert (await _generate(client, tok2, incident_id)).status_code == 404


# ============================== audit ====================================== #
async def test_audit_events(client):
    me, tokens = await create_authenticated_user(client, email="pm9@e.com", username="pmu9")
    token = tokens["access_token"]
    incident_id = await _incident(client, token)
    pm = (await _generate(client, token, incident_id)).json()
    await client.get(f"/v1/postmortems/{pm['id']}", headers=auth_headers(token))
    await client.get(f"/v1/postmortems/{pm['id']}/export?format=pdf", headers=auth_headers(token))
    await _generate(client, token, incident_id, force=True)  # regenerate

    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert {"postmortem_generated", "postmortem_viewed", "postmortem_exported",
            "postmortem_regenerated"} <= actions


async def test_auto_generate_audited(client):
    me, tokens = await create_authenticated_user(client, email="pm10@e.com", username="pmu10")
    token = tokens["access_token"]
    incident_id = await _incident(client, token)
    await client.post(f"/v1/oncall/incidents/{incident_id}/state",
                      headers=auth_headers(token), json={"state": "RESOLVED"})
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert "postmortem_auto_generated" in actions


# ============================== no secret leakage ========================== #
async def test_no_secret_leakage(client):
    _, tokens = await create_authenticated_user(client, email="pm11@e.com", username="pmu11")
    token = tokens["access_token"]
    incident_id = await _incident(client, token)
    pm = (await _generate(client, token, incident_id)).json()
    blob = json.dumps(pm).lower()
    for bad in ("password", "secret", "api_key", "apikey", "credential", "authorization"):
        assert bad not in blob
