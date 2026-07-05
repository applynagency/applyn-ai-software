"""Tests for Sprint 51D - Interactive Product Tour.

Covers default tour seeding (first-login onboarding + role-specific tours),
list with progress, start/resume, step progress tracking, completion tracking,
contextual help, role-audience filtering, tenant + per-user isolation and audit
logging. Strictly additive.
"""

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers


# ============================== seeding / list =========================== #
async def test_default_tours_seeded(client):
    _, t = await create_authenticated_user(client, email="pt1@e.com", username="pt1")
    token = t["access_token"]
    tours = (await client.get("/v1/product-tours", headers=H(token))).json()
    keys = {x["key"] for x in tours}
    assert "first-login-onboarding" in keys
    assert "tour-sre" in keys and "tour-executive" in keys
    fl = next(x for x in tours if x["key"] == "first-login-onboarding")
    assert fl["is_first_login"] is True
    assert fl["step_count"] == 7  # the example flow


async def test_filter_first_login_and_audience(client):
    _, t = await create_authenticated_user(client, email="pt2@e.com", username="pt2")
    token = t["access_token"]
    fl = (await client.get("/v1/product-tours?first_login=true", headers=H(token))).json()
    assert all(x["is_first_login"] for x in fl)
    sre = (await client.get("/v1/product-tours?audience=SRE", headers=H(token))).json()
    assert all(x["audience"] == "SRE" for x in sre)
    bad = await client.get("/v1/product-tours?audience=BOGUS", headers=H(token))
    assert bad.status_code == 400


# ============================== start / resume ========================== #
async def test_start_by_key_and_detail(client):
    _, t = await create_authenticated_user(client, email="pt3@e.com", username="pt3")
    token = t["access_token"]
    r = await client.post("/v1/product-tours/start", headers=H(token),
                          json={"tour_key": "first-login-onboarding"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["progress"]["status"] == "IN_PROGRESS"
    assert len(body["tour"]["steps"]) == 7
    assert body["tour"]["steps"][0]["title"] == "Connect Infrastructure"


async def test_start_requires_identifier(client):
    _, t = await create_authenticated_user(client, email="pt4@e.com", username="pt4")
    token = t["access_token"]
    r = await client.post("/v1/product-tours/start", headers=H(token), json={})
    assert r.status_code == 400


async def test_resume_returns_existing_progress(client):
    _, t = await create_authenticated_user(client, email="pt5@e.com", username="pt5")
    token = t["access_token"]
    start = (await client.post("/v1/product-tours/start", headers=H(token),
                               json={"tour_key": "tour-sre"})).json()
    tour_id = start["tour"]["id"]
    sid = start["tour"]["steps"][0]["id"]
    await client.post(f"/v1/product-tours/{tour_id}/step", headers=H(token), json={"step_id": sid})
    # restart=false should resume with the completed step retained
    again = (await client.post("/v1/product-tours/start", headers=H(token),
                               json={"tour_key": "tour-sre"})).json()
    assert again["progress"]["progress_percent"] > 0
    assert sid in again["progress"]["completed_step_ids"]


async def test_restart_resets_progress(client):
    _, t = await create_authenticated_user(client, email="pt6@e.com", username="pt6")
    token = t["access_token"]
    start = (await client.post("/v1/product-tours/start", headers=H(token),
                               json={"tour_key": "tour-sre"})).json()
    tid = start["tour"]["id"]
    sid = start["tour"]["steps"][0]["id"]
    await client.post(f"/v1/product-tours/{tid}/step", headers=H(token), json={"step_id": sid})
    reset = (await client.post("/v1/product-tours/start", headers=H(token),
                               json={"tour_key": "tour-sre", "restart": True})).json()
    assert reset["progress"]["progress_percent"] == 0
    assert reset["progress"]["completed_step_ids"] == []


# ============================== step progress =========================== #
async def test_step_progress_and_completion(client):
    _, t = await create_authenticated_user(client, email="pt7@e.com", username="pt7")
    token = t["access_token"]
    start = (await client.post("/v1/product-tours/start", headers=H(token),
                               json={"tour_key": "tour-executive"})).json()
    tid = start["tour"]["id"]
    steps = start["tour"]["steps"]
    last = None
    for i, s in enumerate(steps):
        last = (await client.post(f"/v1/product-tours/{tid}/step", headers=H(token),
                                  json={"step_id": s["id"]})).json()
        expected = round(((i + 1) / len(steps)) * 100)
        assert last["progress"]["progress_percent"] == expected
    assert last["progress"]["status"] == "COMPLETED"
    assert last["progress"]["completed_at"] is not None


async def test_step_by_index(client):
    _, t = await create_authenticated_user(client, email="pt8@e.com", username="pt8")
    token = t["access_token"]
    start = (await client.post("/v1/product-tours/start", headers=H(token),
                               json={"tour_key": "tour-developer"})).json()
    tid = start["tour"]["id"]
    res = (await client.post(f"/v1/product-tours/{tid}/step", headers=H(token),
                             json={"step_index": 0})).json()
    assert res["progress"]["current_step_index"] == 1
    assert res["progress"]["progress_percent"] > 0


async def test_step_requires_identifier(client):
    _, t = await create_authenticated_user(client, email="pt9@e.com", username="pt9")
    token = t["access_token"]
    start = (await client.post("/v1/product-tours/start", headers=H(token),
                               json={"tour_key": "tour-sre"})).json()
    tid = start["tour"]["id"]
    r = await client.post(f"/v1/product-tours/{tid}/step", headers=H(token), json={})
    assert r.status_code == 400


# ============================== complete =============================== #
async def test_complete_tour(client):
    _, t = await create_authenticated_user(client, email="pt10@e.com", username="pt10")
    token = t["access_token"]
    start = (await client.post("/v1/product-tours/start", headers=H(token),
                               json={"tour_key": "tour-administrator"})).json()
    tid = start["tour"]["id"]
    done = (await client.post(f"/v1/product-tours/{tid}/complete", headers=H(token))).json()
    assert done["progress"]["status"] == "COMPLETED"
    assert done["progress"]["progress_percent"] == 100


# ============================== contextual help ======================== #
async def test_contextual_help(client):
    _, t = await create_authenticated_user(client, email="pt11@e.com", username="pt11")
    token = t["access_token"]
    by_mod = (await client.get("/v1/product-tours/contextual?module=ai-copilot", headers=H(token))).json()
    assert by_mod["module"] == "ai-copilot"
    assert len(by_mod["steps"]) >= 1

    by_route = (await client.get("/v1/product-tours/contextual?route=/monitoring", headers=H(token))).json()
    assert any(s["target_route"] == "/monitoring" for s in by_route["steps"])

    bad = await client.get("/v1/product-tours/contextual", headers=H(token))
    assert bad.status_code == 400


# ============================== 404 ==================================== #
async def test_get_missing_tour(client):
    _, t = await create_authenticated_user(client, email="pt12@e.com", username="pt12")
    token = t["access_token"]
    assert (await client.get("/v1/product-tours/nope", headers=H(token))).status_code == 404


# ============================== isolation ============================== #
async def test_per_user_and_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="ptA@e.com", username="ptA")
    _, t2 = await create_authenticated_user(client, email="ptB@e.com", username="ptB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    start = (await client.post("/v1/product-tours/start", headers=H(tok1),
                               json={"tour_key": "tour-sre"})).json()
    tid_org1 = start["tour"]["id"]
    sid = start["tour"]["steps"][0]["id"]
    await client.post(f"/v1/product-tours/{tid_org1}/step", headers=H(tok1), json={"step_id": sid})

    # Different org cannot see org1's tour id
    assert (await client.get(f"/v1/product-tours/{tid_org1}", headers=H(tok2))).status_code == 404

    # Same... different user in a different org has independent progress (their own seeded tours)
    tours2 = (await client.get("/v1/product-tours", headers=H(tok2))).json()
    sre2 = next(x for x in tours2 if x["key"] == "tour-sre")
    assert sre2["progress"] is None


# ============================== audit ================================= #
async def test_audit_logging(client):
    me, t = await create_authenticated_user(client, email="pt13@e.com", username="pt13")
    token = t["access_token"]
    start = (await client.post("/v1/product-tours/start", headers=H(token),
                               json={"tour_key": "tour-sre"})).json()
    tid = start["tour"]["id"]
    sid = start["tour"]["steps"][0]["id"]
    await client.post(f"/v1/product-tours/{tid}/step", headers=H(token), json={"step_id": sid})
    await client.post(f"/v1/product-tours/{tid}/complete", headers=H(token))
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert "product_tour_started" in actions
    assert "product_tour_step_completed" in actions
    assert "product_tour_completed" in actions
