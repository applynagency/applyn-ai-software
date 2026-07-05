"""Tests for Sprint 45A — Intelligent Runbooks.

Covers generation (by category and by incident classification), the four step
groups, learning from incident history, versioning (regeneration + manual edit),
search (text + category filter), tenant isolation, and audit logging. Generation
is read-only with respect to incidents.
"""

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.services.runbook import RunbookService
from app.tests.conftest import auth_headers, create_authenticated_user


# ============================== pure classifier =========================== #
def test_classify_categories():
    assert RunbookService.classify("Pod in CrashLoopBackOff, exit code 137") == "CRASHLOOPBACKOFF"
    assert RunbookService.classify("Deployment rollout failed for release v2") == "DEPLOYMENT_FAILURE"
    assert RunbookService.classify("CPU saturation, memory exhausted, scale up") == "CAPACITY"
    assert RunbookService.classify("p99 latency spike, slow response time") == "LATENCY_SPIKE"
    assert RunbookService.classify("Elevated 5xx error rate on api") == "ERROR_SPIKE"
    assert RunbookService.classify("kubernetes node not ready, kubelet down") == "KUBERNETES"
    assert RunbookService.classify("something totally unrelated") == "GENERAL"


# ============================== API helpers =============================== #
async def _generate(client, token, **body):
    return await client.post("/v1/runbooks/generate", headers=auth_headers(token), json=body)


async def _team_agent(client, token):
    team = (await client.post("/v1/ai-teams", headers=auth_headers(token), json={"name": "Ops"})).json()
    await client.post("/v1/ai-team-agents", headers=auth_headers(token),
                      json={"team_id": team["id"], "name": "SRE", "role": "Ops", "instructions": "x",
                            "model": "claude-sonnet", "temperature": 0.2, "max_tokens": 300, "is_active": True})


async def _poll(client, token, alert_name, service="checkout"):
    body = (await client.post("/v1/monitoring/poll", headers=auth_headers(token), json={"alerts": [
        {"provider": "PROMETHEUS", "alert_id": "a1", "alert_name": alert_name,
         "severity": "CRITICAL", "service": service, "environment": "production"}]})).json()
    return body["alerts"][0]["incident_id"]


# ============================== generation ================================ #
async def test_generate_by_category(client):
    _, tokens = await create_authenticated_user(client, email="rb1@e.com", username="rbk1")
    token = tokens["access_token"]
    r = await _generate(client, token, category="KUBERNETES")
    assert r.status_code == 201, r.text
    rb = r.json()
    assert rb["category"] == "KUBERNETES"
    assert rb["version"] == 1 and rb["status"] == "GENERATED" and rb["source"] == "GENERATED"
    assert rb["investigation_steps"] and rb["validation_steps"]
    assert rb["rollback_steps"] and rb["recovery_checklist"]
    assert rb["content_markdown"]


async def test_generate_invalid_category(client):
    _, tokens = await create_authenticated_user(client, email="rb2@e.com", username="rbk2")
    token = tokens["access_token"]
    assert (await _generate(client, token, category="BOGUS")).status_code == 400


async def test_generate_requires_input(client):
    _, tokens = await create_authenticated_user(client, email="rb3@e.com", username="rbk3")
    token = tokens["access_token"]
    assert (await _generate(client, token)).status_code == 400


async def test_generate_from_incident_classifies(client):
    _, tokens = await create_authenticated_user(client, email="rb4@e.com", username="rbk4")
    token = tokens["access_token"]
    await _team_agent(client, token)
    incident_id = await _poll(client, token, "CrashLoopBackOff", "payments")
    rb = (await _generate(client, token, investigation_id=incident_id)).json()
    assert rb["category"] == "CRASHLOOPBACKOFF"
    assert rb["source_incident_count"] >= 1
    assert incident_id in rb["source_incident_ids"]


async def test_unknown_incident_404(client):
    _, tokens = await create_authenticated_user(client, email="rb5@e.com", username="rbk5")
    token = tokens["access_token"]
    assert (await _generate(client, token, investigation_id="nope")).status_code == 404


async def test_learns_from_incident_history(client):
    _, tokens = await create_authenticated_user(client, email="rb6@e.com", username="rbk6")
    token = tokens["access_token"]
    await _team_agent(client, token)
    await _poll(client, token, "Elevated 5xx error rate", "api")
    rb = (await _generate(client, token, category="ERROR_SPIKE")).json()
    assert rb["category"] == "ERROR_SPIKE"
    assert rb["source_incident_count"] >= 1


# ============================== versioning ================================ #
async def test_regeneration_bumps_version(client):
    _, tokens = await create_authenticated_user(client, email="rb7@e.com", username="rbk7")
    token = tokens["access_token"]
    first = (await _generate(client, token, category="LATENCY_SPIKE")).json()
    second = (await _generate(client, token, category="LATENCY_SPIKE")).json()
    assert first["id"] == second["id"]
    assert second["version"] == first["version"] + 1
    assert second["status"] == "REGENERATED"


async def test_manual_edit_versions_and_persists(client):
    _, tokens = await create_authenticated_user(client, email="rb8@e.com", username="rbk8")
    token = tokens["access_token"]
    rb = (await _generate(client, token, category="CAPACITY")).json()
    upd = await client.put(f"/v1/runbooks/{rb['id']}", headers=auth_headers(token), json={
        "title": "Custom Capacity Runbook",
        "investigation_steps": ["Check Grafana capacity dashboard", "Inspect HPA status"],
        "rollback_steps": ["Scale the node pool by +2"],
    })
    assert upd.status_code == 200, upd.text
    out = upd.json()
    assert out["title"] == "Custom Capacity Runbook"
    assert out["version"] == rb["version"] + 1
    assert out["status"] == "EDITED" and out["source"] == "MANUAL"
    assert out["investigation_steps"] == ["Check Grafana capacity dashboard", "Inspect HPA status"]
    assert out["rollback_steps"] == ["Scale the node pool by +2"]
    # validation_steps were not edited → remain populated from generation
    assert out["validation_steps"]
    # re-fetch confirms persistence
    again = (await client.get(f"/v1/runbooks/{rb['id']}", headers=auth_headers(token))).json()
    assert again["title"] == "Custom Capacity Runbook" and again["version"] == out["version"]


# ============================== search ==================================== #
async def test_search_and_category_filter(client):
    _, tokens = await create_authenticated_user(client, email="rb9@e.com", username="rbk9")
    token = tokens["access_token"]
    await _generate(client, token, category="KUBERNETES")
    await _generate(client, token, category="CAPACITY")
    await _generate(client, token, category="ERROR_SPIKE")

    all_rb = (await client.get("/v1/runbooks", headers=auth_headers(token))).json()
    assert all_rb["total"] == 3

    k = (await client.get("/v1/runbooks?search=kubernetes", headers=auth_headers(token))).json()
    assert k["total"] == 1 and k["items"][0]["category"] == "KUBERNETES"

    cap = (await client.get("/v1/runbooks?category=CAPACITY", headers=auth_headers(token))).json()
    assert cap["total"] == 1 and cap["items"][0]["category"] == "CAPACITY"

    # content search hits step text (rollback steps mention "scale")
    scale = (await client.get("/v1/runbooks?search=scale", headers=auth_headers(token))).json()
    assert scale["total"] >= 1


async def test_get_404(client):
    _, tokens = await create_authenticated_user(client, email="rb10@e.com", username="rbk10")
    token = tokens["access_token"]
    assert (await client.get("/v1/runbooks/nope", headers=auth_headers(token))).status_code == 404


# ============================== isolation ================================= #
async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="rbA@e.com", username="rbkA")
    _, t2 = await create_authenticated_user(client, email="rbB@e.com", username="rbkB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    rb = (await _generate(client, tok1, category="KUBERNETES")).json()
    rid = rb["id"]
    assert (await client.get("/v1/runbooks", headers=auth_headers(tok2))).json()["total"] == 0
    assert (await client.get(f"/v1/runbooks/{rid}", headers=auth_headers(tok2))).status_code == 404
    assert (await client.put(f"/v1/runbooks/{rid}", headers=auth_headers(tok2),
                             json={"title": "hijack"})).status_code == 404


# ============================== audit ===================================== #
async def test_audit_logging(client):
    me, tokens = await create_authenticated_user(client, email="rb11@e.com", username="rbk11")
    token = tokens["access_token"]
    rb = (await _generate(client, token, category="DEPLOYMENT_FAILURE")).json()
    await client.get("/v1/runbooks?search=deploy", headers=auth_headers(token))
    await client.put(f"/v1/runbooks/{rb['id']}", headers=auth_headers(token), json={"title": "x"})
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert {"runbook_generated", "runbook_searched", "runbook_updated"} <= actions
