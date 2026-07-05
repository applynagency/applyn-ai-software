"""Tests for Sprint 47C - Guided Setup Wizard.

Covers start/resume, the 10 steps, progress %, auto-detection from real platform
data (integrations, discovery, catalog, dependencies, reports), explicit step
save + resume-later, missing-steps + recommendations, completion summary, tenant
isolation, and audit logging.
"""

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers

STEPS = [
    "ORGANIZATION_SETUP", "CONNECT_INFRASTRUCTURE", "CONNECT_MONITORING",
    "CONNECT_SOURCE_CONTROL", "RUN_DISCOVERY", "GENERATE_SERVICE_CATALOG",
    "GENERATE_DEPENDENCY_GRAPH", "GENERATE_RELIABILITY_REPORT",
    "GENERATE_DEPLOYMENT_RISK_REPORT", "FINISH",
]


async def _start(client, token, force_new=False):
    return await client.post("/v1/onboarding/start", headers=H(token),
                             json={"force_new": force_new})


# ============================== start / resume =========================== #
async def test_start_creates_session(client):
    _, t = await create_authenticated_user(client, email="ob1@e.com", username="ob1")
    token = t["access_token"]
    r = await _start(client, token)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "IN_PROGRESS"
    assert len(body["steps"]) == 10
    assert [s["key"] for s in body["steps"]] == STEPS
    # org setup auto-complete, others missing
    assert "ORGANIZATION_SETUP" in body["completed_steps"]
    assert body["progress_percent"] >= 10
    assert body["recommendations"] and body["missing_steps"]


async def test_start_resumes_existing(client):
    _, t = await create_authenticated_user(client, email="ob2@e.com", username="ob2")
    token = t["access_token"]
    first = (await _start(client, token)).json()
    again = (await _start(client, token)).json()
    assert again["id"] == first["id"]  # resumed, not duplicated
    forced = (await _start(client, token, force_new=True)).json()
    assert forced["id"] != first["id"]


# ============================== auto-detection =========================== #
async def test_progress_autodetects_from_platform(client):
    _, t = await create_authenticated_user(client, email="ob3@e.com", username="ob3")
    token = t["access_token"]
    sess = (await _start(client, token)).json()
    sid = sess["id"]

    # connect infra (cloud) + monitoring (observability) + source control via marketplace
    await client.post("/v1/integrations/connect", headers=H(token), json={
        "integration_key": "AWS", "credentials": {"access_key": "a", "secret_key": "s", "region": "us-east-1"}})
    await client.post("/v1/integrations/connect", headers=H(token), json={
        "integration_key": "DATADOG", "credentials": {"api_key": "k", "app_key": "a"}})
    await client.post("/v1/integrations/connect", headers=H(token), json={
        "integration_key": "GITHUB", "credentials": {"token": "ghp"}})

    # run discovery across connected integrations (creates a scan run)
    await client.post("/v1/discovery/sync", headers=H(token), json={})

    # service catalog + dependency graph via their canonical endpoints
    checkout = (await client.post("/v1/services", headers=H(token),
                                  json={"name": "checkout", "tier": "TIER_2"})).json()["id"]
    orders_db = (await client.post("/v1/services", headers=H(token),
                                   json={"name": "orders-db", "tier": "TIER_2"})).json()["id"]
    await client.post("/v1/service-dependencies", headers=H(token), json={
        "source_service_id": checkout, "target_service_id": orders_db,
        "dependency_type": "DATASTORE"})

    body = (await client.get(f"/v1/onboarding/{sid}", headers=H(token))).json()
    done = set(body["completed_steps"])
    assert {"CONNECT_INFRASTRUCTURE", "CONNECT_MONITORING", "CONNECT_SOURCE_CONTROL",
            "RUN_DISCOVERY", "GENERATE_SERVICE_CATALOG", "GENERATE_DEPENDENCY_GRAPH"} <= done
    # those steps show as auto-detected
    infra = next(s for s in body["steps"] if s["key"] == "CONNECT_INFRASTRUCTURE")
    assert infra["completed"] and infra["auto_detected"]
    assert body["progress_percent"] >= 70


async def test_reliability_and_risk_steps_autodetect(client):
    _, t = await create_authenticated_user(client, email="ob4@e.com", username="ob4")
    token = t["access_token"]
    sess = (await _start(client, token)).json()
    # reliability assessment + change-failure prediction
    await client.post("/v1/reliability/analyze", headers=H(token), json={})
    await client.post("/v1/change-failure-prediction/analyze", headers=H(token), json={
        "service": "checkout", "environment": "production", "commit_count": 3, "changed_files": 5})
    body = (await client.get(f"/v1/onboarding/{sess['id']}", headers=H(token))).json()
    done = set(body["completed_steps"])
    assert "GENERATE_RELIABILITY_REPORT" in done
    assert "GENERATE_DEPLOYMENT_RISK_REPORT" in done


# ============================== explicit step + resume =================== #
async def test_explicit_step_save_and_resume(client):
    _, t = await create_authenticated_user(client, email="ob5@e.com", username="ob5")
    token = t["access_token"]
    sess = (await _start(client, token)).json()
    sid = sess["id"]
    r = await client.post(f"/v1/onboarding/{sid}/step", headers=H(token), json={
        "step": "CONNECT_INFRASTRUCTURE", "completed": True, "data": {"note": "manual"}})
    assert r.status_code == 200, r.text
    assert "CONNECT_INFRASTRUCTURE" in r.json()["completed_steps"]
    # resume reflects the saved step
    again = (await client.get(f"/v1/onboarding/{sid}", headers=H(token))).json()
    assert "CONNECT_INFRASTRUCTURE" in again["completed_steps"]
    # un-mark
    r2 = await client.post(f"/v1/onboarding/{sid}/step", headers=H(token), json={
        "step": "CONNECT_INFRASTRUCTURE", "completed": False})
    assert "CONNECT_INFRASTRUCTURE" not in r2.json()["completed_steps"]


async def test_unknown_step_rejected(client):
    _, t = await create_authenticated_user(client, email="ob6@e.com", username="ob6")
    token = t["access_token"]
    sess = (await _start(client, token)).json()
    r = await client.post(f"/v1/onboarding/{sess['id']}/step", headers=H(token),
                          json={"step": "NONSENSE"})
    assert r.status_code == 422


# ============================== complete ================================= #
async def test_complete_generates_summary(client):
    _, t = await create_authenticated_user(client, email="ob7@e.com", username="ob7")
    token = t["access_token"]
    sess = (await _start(client, token)).json()
    r = await client.post(f"/v1/onboarding/{sess['id']}/complete", headers=H(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "COMPLETED"
    assert "FINISH" in body["completed_steps"]
    assert body["summary"] and "Onboarding summary" in body["summary"]
    # a completed session is not resumed by start
    nxt = (await _start(client, token)).json()
    assert nxt["id"] != sess["id"]


# ============================== 404 + isolation ========================== #
async def test_get_404(client):
    _, t = await create_authenticated_user(client, email="ob8@e.com", username="ob8")
    token = t["access_token"]
    assert (await client.get("/v1/onboarding/nope", headers=H(token))).status_code == 404


async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="obA@e.com", username="obA")
    _, t2 = await create_authenticated_user(client, email="obB@e.com", username="obB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    sess = (await _start(client, tok1)).json()
    assert (await client.get(f"/v1/onboarding/{sess['id']}", headers=H(tok2))).status_code == 404
    assert (await client.post(f"/v1/onboarding/{sess['id']}/step", headers=H(tok2),
                              json={"step": "FINISH"})).status_code == 404
    assert (await client.post(f"/v1/onboarding/{sess['id']}/complete",
                              headers=H(tok2))).status_code == 404


# ============================== audit ==================================== #
async def test_audit_logging(client):
    me, t = await create_authenticated_user(client, email="obC@e.com", username="obC")
    token = t["access_token"]
    sess = (await _start(client, token)).json()
    await client.post(f"/v1/onboarding/{sess['id']}/step", headers=H(token),
                      json={"step": "CONNECT_MONITORING"})
    await client.post(f"/v1/onboarding/{sess['id']}/complete", headers=H(token))
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert {"onboarding_started", "onboarding_step_updated", "onboarding_completed"} <= actions
