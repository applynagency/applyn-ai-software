"""Tests for Sprint 51B - Test Playbook Engine.

Covers playbook CRUD with ordered steps, category validation, list/search,
execution tracking (pass/fail/partial aggregation), run reporting, markdown/
html/pdf export, the default validation library (idempotent seeding), tenant
isolation and audit logging. Strictly additive.
"""

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers


# ============================== helpers =================================== #
async def _create(client, token, **over):
    body = {
        "name": "Monitoring Smoke",
        "category": "MONITORING",
        "description": "Validate monitoring",
        "preconditions": "Service exists",
        "steps": [
            {"title": "Send alert", "expected_result": "Incident created"},
            {"title": "Verify incident", "expected_result": "Incident visible"},
        ],
        **over,
    }
    return await client.post("/v1/test-playbooks", headers=H(token), json=body)


async def _execute(client, token, pid, results, notes=None):
    body = {"step_results": results}
    if notes:
        body["notes"] = notes
    return await client.post(f"/v1/test-playbooks/{pid}/execute", headers=H(token), json=body)


# ============================== create / read ============================= #
async def test_create_playbook_with_steps(client):
    _, t = await create_authenticated_user(client, email="pb1@e.com", username="pb1")
    token = t["access_token"]
    r = await _create(client, token)
    assert r.status_code == 201, r.text
    pb = r.json()
    assert pb["category"] == "MONITORING"
    assert len(pb["steps"]) == 2
    assert pb["steps"][0]["order_index"] == 0


async def test_invalid_category_rejected(client):
    _, t = await create_authenticated_user(client, email="pb2@e.com", username="pb2")
    token = t["access_token"]
    r = await _create(client, token, category="NOPE")
    assert r.status_code == 400


async def test_list_and_filter(client):
    _, t = await create_authenticated_user(client, email="pb3@e.com", username="pb3")
    token = t["access_token"]
    await _create(client, token, name="Mon A", category="MONITORING")
    await _create(client, token, name="SLO B", category="SLO")
    allres = (await client.get("/v1/test-playbooks", headers=H(token))).json()
    assert len(allres) >= 2
    slo = (await client.get("/v1/test-playbooks?category=SLO", headers=H(token))).json()
    assert all(p["category"] == "SLO" for p in slo)
    found = (await client.get("/v1/test-playbooks?search=Mon", headers=H(token))).json()
    assert any(p["name"] == "Mon A" for p in found)


async def test_get_detail_and_404(client):
    _, t = await create_authenticated_user(client, email="pb4@e.com", username="pb4")
    token = t["access_token"]
    pb = (await _create(client, token)).json()
    detail = (await client.get(f"/v1/test-playbooks/{pb['id']}", headers=H(token))).json()
    assert detail["id"] == pb["id"]
    assert (await client.get("/v1/test-playbooks/nope", headers=H(token))).status_code == 404


# ============================== execution =============================== #
async def test_execute_all_pass(client):
    _, t = await create_authenticated_user(client, email="pb5@e.com", username="pb5")
    token = t["access_token"]
    pb = (await _create(client, token)).json()
    sids = [s["id"] for s in pb["steps"]]
    r = await _execute(client, token, pb["id"],
                       [{"step_id": s, "status": "PASSED"} for s in sids])
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "PASSED"
    assert run["pass_rate"] == 100
    assert run["passed_steps"] == 2


async def test_execute_with_failure(client):
    _, t = await create_authenticated_user(client, email="pb6@e.com", username="pb6")
    token = t["access_token"]
    pb = (await _create(client, token)).json()
    sids = [s["id"] for s in pb["steps"]]
    run = (await _execute(client, token, pb["id"], [
        {"step_id": sids[0], "status": "PASSED"},
        {"step_id": sids[1], "status": "FAILED", "actual_result": "no incident", "notes": "broken"},
    ])).json()
    assert run["status"] == "FAILED"
    assert run["failed_steps"] == 1
    assert run["pass_rate"] == 50


async def test_execute_partial_when_unreported(client):
    _, t = await create_authenticated_user(client, email="pb7@e.com", username="pb7")
    token = t["access_token"]
    pb = (await _create(client, token)).json()
    sids = [s["id"] for s in pb["steps"]]
    run = (await _execute(client, token, pb["id"],
                          [{"step_id": sids[0], "status": "PASSED"}])).json()
    assert run["status"] == "PARTIAL"
    assert run["skipped_steps"] == 1


async def test_execute_invalid_step_status(client):
    _, t = await create_authenticated_user(client, email="pb8@e.com", username="pb8")
    token = t["access_token"]
    pb = (await _create(client, token)).json()
    sid = pb["steps"][0]["id"]
    r = await _execute(client, token, pb["id"], [{"step_id": sid, "status": "MAYBE"}])
    assert r.status_code == 400


async def test_execute_no_steps_rejected(client):
    _, t = await create_authenticated_user(client, email="pb9@e.com", username="pb9")
    token = t["access_token"]
    pb = (await _create(client, token, steps=[])).json()
    r = await _execute(client, token, pb["id"], [])
    assert r.status_code == 400


# ============================== runs / report ============================ #
async def test_get_run_and_export(client):
    _, t = await create_authenticated_user(client, email="pb10@e.com", username="pb10")
    token = t["access_token"]
    pb = (await _create(client, token)).json()
    sids = [s["id"] for s in pb["steps"]]
    run = (await _execute(client, token, pb["id"],
                          [{"step_id": s, "status": "PASSED"} for s in sids])).json()

    got = (await client.get(f"/v1/test-playbooks/runs/{run['id']}", headers=H(token))).json()
    assert got["id"] == run["id"]
    assert len(got["results"]) == 2

    md = await client.get(f"/v1/test-playbooks/runs/{run['id']}/export?format=markdown", headers=H(token))
    assert md.status_code == 200
    assert "Test Report" in md.text

    pdf = await client.get(f"/v1/test-playbooks/runs/{run['id']}/export?format=pdf", headers=H(token))
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"

    bad = await client.get(f"/v1/test-playbooks/runs/{run['id']}/export?format=xls", headers=H(token))
    assert bad.status_code == 400


async def test_run_404(client):
    _, t = await create_authenticated_user(client, email="pb11@e.com", username="pb11")
    token = t["access_token"]
    assert (await client.get("/v1/test-playbooks/runs/nope", headers=H(token))).status_code == 404


# ============================== update / delete ========================== #
async def test_update_and_delete(client):
    _, t = await create_authenticated_user(client, email="pb12@e.com", username="pb12")
    token = t["access_token"]
    pb = (await _create(client, token)).json()
    upd = (await client.put(f"/v1/test-playbooks/{pb['id']}", headers=H(token),
                            json={"name": "Renamed", "steps": [{"title": "only step"}]})).json()
    assert upd["name"] == "Renamed"
    assert len(upd["steps"]) == 1
    d = await client.delete(f"/v1/test-playbooks/{pb['id']}", headers=H(token))
    assert d.status_code == 204
    assert (await client.get(f"/v1/test-playbooks/{pb['id']}", headers=H(token))).status_code == 404


# ============================== default library ========================== #
async def test_seed_library_idempotent(client):
    _, t = await create_authenticated_user(client, email="pb13@e.com", username="pb13")
    token = t["access_token"]
    first = (await client.post("/v1/test-playbooks/seed-library", headers=H(token))).json()
    assert len(first) == 9
    cats = {p["category"] for p in first}
    assert "AI_COPILOT" in cats and "MONITORING" in cats
    second = (await client.post("/v1/test-playbooks/seed-library", headers=H(token))).json()
    assert second == []
    listed = (await client.get("/v1/test-playbooks", headers=H(token))).json()
    assert len(listed) >= 9


# ============================== isolation =============================== #
async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="pbA@e.com", username="pbA")
    _, t2 = await create_authenticated_user(client, email="pbB@e.com", username="pbB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    pb = (await _create(client, tok1, name="Org1 Playbook")).json()
    sids = [s["id"] for s in pb["steps"]]
    run = (await _execute(client, tok1, pb["id"],
                          [{"step_id": s, "status": "PASSED"} for s in sids])).json()
    assert (await client.get(f"/v1/test-playbooks/{pb['id']}", headers=H(tok2))).status_code == 404
    assert (await client.get(f"/v1/test-playbooks/runs/{run['id']}", headers=H(tok2))).status_code == 404
    assert (await client.get("/v1/test-playbooks", headers=H(tok2))).json() == []


# ============================== audit ================================== #
async def test_audit_logging(client):
    me, t = await create_authenticated_user(client, email="pb14@e.com", username="pb14")
    token = t["access_token"]
    pb = (await _create(client, token)).json()
    sids = [s["id"] for s in pb["steps"]]
    run = (await _execute(client, token, pb["id"],
                          [{"step_id": s, "status": "PASSED"} for s in sids])).json()
    await client.get(f"/v1/test-playbooks/runs/{run['id']}/export?format=pdf", headers=H(token))
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert "test_playbook_created" in actions
    assert "test_playbook_executed" in actions
    assert "test_playbook_report_exported" in actions
