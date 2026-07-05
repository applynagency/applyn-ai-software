"""Sprint 52C.1 — Demo Scenario Engine tests.

Validates:
* Scenario seeding (5 built-in scenarios)
* Scenario listing and retrieval
* All 5 scenario execution flows (CHECKOUT_OUTAGE, DATABASE_LATENCY,
  MEMORY_LEAK, BAD_DEPLOYMENT, COST_EXPLOSION)
* Replay mode (preserves timeline, generates new run row)
* Reset (clears runs, resets run_count)
* Tenant isolation (org A cannot see org B scenarios)
* Guided walkthrough (10 steps)
* Screenshot manifest
* Sales demo mode dashboard
* Audit logging
"""

from sqlalchemy import func, select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.incident import IncidentInvestigation, MonitoringAlert
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers

BASE_SCENARIOS = "/v1/demo-scenarios"
BASE_WT = "/v1/demo-walkthroughs"
BASE_SALES = "/v1/demo/sales-mode"
BASE_DEMO_ORG = "/v1/demo-organizations"


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
async def _new_user(client, n: str):
    me, t = await create_authenticated_user(
        client, email=f"sc{n}@e.com", username=f"sc{n}"
    )
    return me, t["access_token"]


async def _create_demo_org(client, token, template="ecommerce"):
    r = await client.post(BASE_DEMO_ORG, headers=H(token), json={"template": template})
    assert r.status_code == 201, r.text
    return r.json()


async def _seed(client, token, org_id):
    r = await client.post(
        f"{BASE_SCENARIOS}/seed",
        headers={**H(token), "X-Organization-Id": org_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _get_scenario_id(client, token, org_id, stype: str) -> str:
    r = await client.get(
        BASE_SCENARIOS,
        headers={**H(token), "X-Organization-Id": org_id},
    )
    assert r.status_code == 200, r.text
    for s in r.json()["items"]:
        if s["scenario_type"] == stype:
            return s["id"]
    raise AssertionError(f"Scenario type {stype} not found")


async def _run(client, token, org_id, scenario_id):
    r = await client.post(
        f"{BASE_SCENARIOS}/{scenario_id}/run",
        headers={**H(token), "X-Organization-Id": org_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


# -----------------------------------------------------------------------
# Scenario seeding
# -----------------------------------------------------------------------
async def test_seed_creates_five_scenarios(client):
    _, token = await _new_user(client, "seed1")
    demo_org = await _create_demo_org(client, token)
    org_id = demo_org["id"]
    created = await _seed(client, token, org_id)
    assert len(created) == 5
    types = {s["scenario_type"] for s in created}
    assert types == {
        "CHECKOUT_OUTAGE", "DATABASE_LATENCY",
        "MEMORY_LEAK", "BAD_DEPLOYMENT", "COST_EXPLOSION",
    }


async def test_seed_is_idempotent(client):
    _, token = await _new_user(client, "seed2")
    org_id = (await _create_demo_org(client, token))["id"]
    await _seed(client, token, org_id)
    second = await _seed(client, token, org_id)
    # Second seed returns empty list — nothing duplicated.
    assert second == []


async def test_list_scenarios(client):
    _, token = await _new_user(client, "list1")
    org_id = (await _create_demo_org(client, token))["id"]
    await _seed(client, token, org_id)
    r = await client.get(BASE_SCENARIOS, headers={**H(token), "X-Organization-Id": org_id})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 5
    for s in data["items"]:
        assert s["is_builtin"] is True
        assert s["flow_steps"]


# -----------------------------------------------------------------------
# Scenario execution — all 5 types
# -----------------------------------------------------------------------
async def test_run_checkout_outage(client):
    _, token = await _new_user(client, "co1")
    org_id = (await _create_demo_org(client, token))["id"]
    await _seed(client, token, org_id)
    sc_id = await _get_scenario_id(client, token, org_id, "CHECKOUT_OUTAGE")
    run = await _run(client, token, org_id, sc_id)
    assert run["status"] == "COMPLETED"
    assert run["completed_steps"] == 10
    assert run["incident_ids"]
    assert run["alert_ids"]
    # Verify generated rows in DB
    async with AsyncSessionLocal() as session:
        inc_count = (await session.execute(
            select(func.count()).select_from(IncidentInvestigation)
            .where(IncidentInvestigation.id.in_(run["incident_ids"]))
        )).scalar()
        alert_count = (await session.execute(
            select(func.count()).select_from(MonitoringAlert)
            .where(MonitoringAlert.id.in_(run["alert_ids"]))
        )).scalar()
    assert inc_count >= 1
    assert alert_count >= 1


async def test_run_database_latency(client):
    _, token = await _new_user(client, "dl1")
    org_id = (await _create_demo_org(client, token))["id"]
    await _seed(client, token, org_id)
    sc_id = await _get_scenario_id(client, token, org_id, "DATABASE_LATENCY")
    run = await _run(client, token, org_id, sc_id)
    assert run["status"] == "COMPLETED"
    assert run["completed_steps"] == 7
    assert run["incident_ids"]


async def test_run_memory_leak(client):
    _, token = await _new_user(client, "ml1")
    org_id = (await _create_demo_org(client, token))["id"]
    await _seed(client, token, org_id)
    sc_id = await _get_scenario_id(client, token, org_id, "MEMORY_LEAK")
    run = await _run(client, token, org_id, sc_id)
    assert run["status"] == "COMPLETED"
    assert run["completed_steps"] == 7
    assert len(run["alert_ids"]) >= 2


async def test_run_bad_deployment(client):
    _, token = await _new_user(client, "bd1")
    org_id = (await _create_demo_org(client, token))["id"]
    await _seed(client, token, org_id)
    sc_id = await _get_scenario_id(client, token, org_id, "BAD_DEPLOYMENT")
    run = await _run(client, token, org_id, sc_id)
    assert run["status"] == "COMPLETED"
    assert run["completed_steps"] == 5
    ds = [e for e in run["generated_events"] if e.get("type") == "deployment_safety"]
    assert ds
    assert ds[0]["readiness"] == "NOT_READY"


async def test_run_cost_explosion(client):
    _, token = await _new_user(client, "ce1")
    org_id = (await _create_demo_org(client, token))["id"]
    await _seed(client, token, org_id)
    sc_id = await _get_scenario_id(client, token, org_id, "COST_EXPLOSION")
    run = await _run(client, token, org_id, sc_id)
    assert run["status"] == "COMPLETED"
    assert run["completed_steps"] == 5
    ce = [e for e in run["generated_events"] if e.get("type") == "cost_analysis"]
    assert ce
    assert ce[0]["waste_usd"] == 14820


# -----------------------------------------------------------------------
# Replay
# -----------------------------------------------------------------------
async def test_replay_creates_new_run(client):
    _, token = await _new_user(client, "rep1")
    org_id = (await _create_demo_org(client, token))["id"]
    await _seed(client, token, org_id)
    sc_id = await _get_scenario_id(client, token, org_id, "CHECKOUT_OUTAGE")
    first = await _run(client, token, org_id, sc_id)
    r = await client.post(
        f"{BASE_SCENARIOS}/{sc_id}/replay",
        headers={**H(token), "X-Organization-Id": org_id},
        json={},
    )
    assert r.status_code == 201, r.text
    replay = r.json()
    assert replay["is_replay"] is True
    assert replay["replayed_from_id"] == first["id"]
    assert replay["id"] != first["id"]
    assert replay["status"] == "COMPLETED"
    assert replay["completed_steps"] == first["completed_steps"]


async def test_replay_with_explicit_run_id(client):
    _, token = await _new_user(client, "rep2")
    org_id = (await _create_demo_org(client, token))["id"]
    await _seed(client, token, org_id)
    sc_id = await _get_scenario_id(client, token, org_id, "CHECKOUT_OUTAGE")
    first = await _run(client, token, org_id, sc_id)
    r = await client.post(
        f"{BASE_SCENARIOS}/{sc_id}/replay",
        headers={**H(token), "X-Organization-Id": org_id},
        json={"run_id": first["id"]},
    )
    assert r.status_code == 201
    assert r.json()["replayed_from_id"] == first["id"]


# -----------------------------------------------------------------------
# Reset
# -----------------------------------------------------------------------
async def test_reset_clears_runs(client):
    _, token = await _new_user(client, "rst1")
    org_id = (await _create_demo_org(client, token))["id"]
    await _seed(client, token, org_id)
    sc_id = await _get_scenario_id(client, token, org_id, "CHECKOUT_OUTAGE")
    await _run(client, token, org_id, sc_id)
    # Verify run exists
    runs_before = (await client.get(
        f"{BASE_SCENARIOS}/{sc_id}/runs",
        headers={**H(token), "X-Organization-Id": org_id},
    )).json()
    assert runs_before["total"] >= 1

    r = await client.post(
        f"{BASE_SCENARIOS}/{sc_id}/reset",
        headers={**H(token), "X-Organization-Id": org_id},
    )
    assert r.status_code == 200
    assert r.json()["run_count"] == 0
    assert r.json()["status"] == "AVAILABLE"

    runs_after = (await client.get(
        f"{BASE_SCENARIOS}/{sc_id}/runs",
        headers={**H(token), "X-Organization-Id": org_id},
    )).json()
    assert runs_after["total"] == 0


# -----------------------------------------------------------------------
# Run listing
# -----------------------------------------------------------------------
async def test_list_runs(client):
    _, token = await _new_user(client, "lr1")
    org_id = (await _create_demo_org(client, token))["id"]
    await _seed(client, token, org_id)
    sc_id = await _get_scenario_id(client, token, org_id, "CHECKOUT_OUTAGE")
    await _run(client, token, org_id, sc_id)
    await _run(client, token, org_id, sc_id)  # second run
    r = await client.get(
        f"{BASE_SCENARIOS}/runs",
        headers={**H(token), "X-Organization-Id": org_id},
    )
    assert r.status_code == 200
    assert r.json()["total"] >= 2


# -----------------------------------------------------------------------
# Tenant isolation
# -----------------------------------------------------------------------
async def test_tenant_isolation(client):
    _, token_a = await _new_user(client, "iso_a")
    _, token_b = await _new_user(client, "iso_b")
    org_a = (await _create_demo_org(client, token_a))["id"]
    org_b = (await _create_demo_org(client, token_b))["id"]
    await _seed(client, token_a, org_a)
    await _seed(client, token_b, org_b)
    sc_id_a = await _get_scenario_id(client, token_a, org_a, "CHECKOUT_OUTAGE")
    # User B cannot access User A's scenario
    r = await client.get(
        f"{BASE_SCENARIOS}/{sc_id_a}",
        headers={**H(token_b), "X-Organization-Id": org_b},
    )
    assert r.status_code == 404


# -----------------------------------------------------------------------
# Walkthrough
# -----------------------------------------------------------------------
async def test_get_walkthrough(client):
    _, token = await _new_user(client, "wt1")
    org_id = (await _create_demo_org(client, token))["id"]
    r = await client.get(
        BASE_WT,
        headers={**H(token), "X-Organization-Id": org_id},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total_steps"] == 10
    steps = data["steps"]
    assert len(steps) == 10
    modules = [s["module"] for s in steps]
    assert "discovery" in modules
    assert "incidents" in modules
    assert "postmortems" in modules
    assert "capacity-cost" in modules
    for s in steps:
        assert s["description"]
        assert s["expected_result"]
        assert s["next_action"]
        assert s["screenshot_url"]
        assert s["callout"]


async def test_get_screenshots_manifest(client):
    _, token = await _new_user(client, "wt2")
    r = await client.get(f"{BASE_WT}/screenshots", headers=H(token))
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 10
    filenames = [a["filename"] for a in data["assets"]]
    assert "01-discovery-dashboard.png" in filenames
    assert "08-postmortem-report.png" in filenames
    assert "10-capacity-cost.png" in filenames


# -----------------------------------------------------------------------
# Sales Demo Mode
# -----------------------------------------------------------------------
async def test_sales_mode_no_orgs(client):
    _, token = await _new_user(client, "sm1")
    r = await client.get(BASE_SALES, headers=H(token))
    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == "SALES_DEMO"
    assert data["presentation_mode"] is True
    assert data["total_walkthrough_steps"] == 10
    assert data["value_callouts"]
    assert data["screenshot_manifest"]["total"] == 10
    assert "SIMULATED" in data["simulated_credentials_note"]


async def test_sales_mode_with_demo_org(client):
    _, token = await _new_user(client, "sm2")
    org_id = (await _create_demo_org(client, token))["id"]
    await _seed(client, token, org_id)
    # Run two scenarios
    sc_id = await _get_scenario_id(client, token, org_id, "CHECKOUT_OUTAGE")
    await _run(client, token, org_id, sc_id)
    r = await client.get(BASE_SALES, headers=H(token))
    assert r.status_code == 200
    data = r.json()
    assert data["total_demo_orgs"] >= 1
    assert data["total_scenarios"] >= 5
    assert data["completed_runs"] >= 1
    org_ids = {o["id"] for o in data["demo_organizations"]}
    assert org_id in org_ids


async def test_sales_mode_navigation(client):
    _, token = await _new_user(client, "sm3")
    r = await client.get(BASE_SALES, headers=H(token))
    nav = r.json()["navigation"]
    paths = [n["path"] for n in nav]
    assert "/v1/demo-organizations" in paths
    assert "/v1/demo-scenarios" in paths
    assert "/v1/demo-walkthroughs" in paths


# -----------------------------------------------------------------------
# Audit logging
# -----------------------------------------------------------------------
async def test_audit_logging(client):
    me, token = await _new_user(client, "aud1")
    org_id = (await _create_demo_org(client, token))["id"]
    await _seed(client, token, org_id)
    sc_id = await _get_scenario_id(client, token, org_id, "CHECKOUT_OUTAGE")
    await _run(client, token, org_id, sc_id)
    r = await client.post(
        f"{BASE_SCENARIOS}/{sc_id}/replay",
        headers={**H(token), "X-Organization-Id": org_id},
        json={},
    )
    assert r.status_code == 201
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(
                select(AuditLog.action).where(AuditLog.user_id == me["id"])
            )).scalars().all()
        )
    assert "demo_scenario.run" in actions
    assert "demo_scenario.replay" in actions


# -----------------------------------------------------------------------
# Success criteria end-to-end: full prospect journey
# -----------------------------------------------------------------------
async def test_full_prospect_journey(client):
    """
    A prospect can:
    1. Create Demo Organization
    2. Run Checkout Failure Scenario
    3. View Timeline (via incident_ids in run)
    4. View Root Cause (incident has root_cause set)
    5. View Recommendations (IncidentRecommendation rows exist)
    6. View Remediation (IncidentRemediationAction rows exist)
    7. View Postmortem (IncidentPostmortem rows exist)
    8. Complete Guided Walkthrough (10 steps returned)
    """
    from app.models.incident import IncidentRecommendation, IncidentRemediationAction
    from app.models.postmortem import IncidentPostmortem

    _, token = await _new_user(client, "journey")
    # 1. Create demo org
    org_id = (await _create_demo_org(client, token, "ecommerce"))["id"]
    await _seed(client, token, org_id)
    # 2. Run Checkout Outage scenario
    sc_id = await _get_scenario_id(client, token, org_id, "CHECKOUT_OUTAGE")
    run = await _run(client, token, org_id, sc_id)
    assert run["status"] == "COMPLETED"
    inc_id = run["incident_ids"][0]
    # 3 & 4. Timeline + root cause
    async with AsyncSessionLocal() as session:
        inv = await session.get(IncidentInvestigation, inc_id)
        assert inv.root_cause
        assert inv.confidence_score >= 80
        # 5. Recommendations
        from sqlalchemy import select as _sel
        recs = (await session.execute(
            _sel(func.count()).select_from(IncidentRecommendation)
            .where(IncidentRecommendation.investigation_id == inc_id)
        )).scalar()
        assert recs >= 2
        # 6. Remediation
        actions = (await session.execute(
            _sel(func.count()).select_from(IncidentRemediationAction)
            .where(IncidentRemediationAction.investigation_id == inc_id)
        )).scalar()
        assert actions >= 1
        # 7. Postmortem
        pm = (await session.execute(
            _sel(func.count()).select_from(IncidentPostmortem)
            .where(IncidentPostmortem.investigation_id == inc_id)
        )).scalar()
        assert pm >= 1
    # 8. Guided walkthrough
    wt = (await client.get(
        BASE_WT,
        headers={**H(token), "X-Organization-Id": org_id},
    )).json()
    assert wt["total_steps"] == 10
