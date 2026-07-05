"""Tests for Sprint 52C — Demo Organization Generator.

Covers template listing, demo organization creation across all 5 templates,
full subsystem population (services, SLOs, dependency graph, AI teams/agents/
workflows, alerts, incidents + remediation + war rooms + postmortems, capacity
metrics/forecasts, cost reports, deployment history), regenerate/reset, delete,
multiple demo orgs, ownership enforcement, and tenant isolation. Strictly
additive — reuses existing models.
"""

from sqlalchemy import func, select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.incident import IncidentInvestigation, MonitoringAlert
from app.models.slo import Service
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers
BASE = "/v1/demo-organizations"


async def _new_user(client, n):
    me, t = await create_authenticated_user(client, email=f"demo{n}@e.com", username=f"demo{n}")
    return me, t["access_token"]


async def _create(client, token, template="ecommerce", name=None):
    body = {"template": template}
    if name:
        body["name"] = name
    return await client.post(BASE, headers=H(token), json=body)


# ============================== templates ============================== #
async def test_list_templates(client):
    _, token = await _new_user(client, "tpl")
    r = await client.get(f"{BASE}/templates", headers=H(token))
    assert r.status_code == 200, r.text
    keys = {t["key"] for t in r.json()["templates"]}
    assert keys == {"ecommerce", "fintech", "healthcare", "saas", "microservices"}
    for t in r.json()["templates"]:
        assert t["service_count"] >= 5
        assert t["incident_count"] >= 1
        assert t["highlights"]


# ============================== creation =============================== #
async def test_create_populates_all_subsystems(client):
    _, token = await _new_user(client, "create")
    r = await _create(client, token, "ecommerce")
    assert r.status_code == 201, r.text
    s = r.json()
    c = s["counts"]
    assert s["template"] == "ecommerce"
    assert s["slug"].startswith("demo-ecommerce-")
    # Every validation subsystem must be populated.
    assert c["services"] >= 6
    assert c["applications"] >= c["services"]  # app inventory mirrors seeded services
    assert c["slos"] >= c["services"]  # availability + latency per service
    assert c["dependencies"] >= 5
    assert c["teams"] >= 3
    assert c["ai_teams"] == 1
    assert c["ai_agents"] >= 4
    assert c["workflows"] >= 1
    assert c["alerts"] >= 4
    assert c["incidents"] >= 2
    assert c["remediation_actions"] >= 1
    assert c["war_rooms"] >= 1
    assert c["postmortems"] >= 1
    assert c["capacity_metrics"] >= 10
    assert c["capacity_forecasts"] >= 2
    assert c["cost_reports"] >= 1
    assert c["deployments"] >= 4
    assert c["demo_assets"] >= 6
    # Demo assets in the summary.
    assert "no real" in s["credentials"]["note"].lower()
    assert s["credentials"]["simulated_integrations"]
    assert s["dashboards"] and s["screenshots"] and s["reports"]


async def test_all_templates_create(client):
    for i, tpl in enumerate(["fintech", "healthcare", "saas", "microservices"]):
        _, token = await _new_user(client, f"all{i}")
        r = await _create(client, token, tpl)
        assert r.status_code == 201, r.text
        c = r.json()["counts"]
        assert c["services"] >= 5
        assert c["applications"] >= c["services"]
        assert c["teams"] >= 2
        assert c["incidents"] >= 1
        assert c["cost_reports"] >= 1
        assert c["capacity_forecasts"] >= 1
        assert c["deployments"] >= 1
        assert c["dependencies"] >= 1
        assert c["demo_assets"] >= 6


async def test_invalid_template(client):
    _, token = await _new_user(client, "bad")
    r = await _create(client, token, "spaceship")
    assert r.status_code == 422


# ============================== list / multiple ======================== #
async def test_list_and_multiple_demo_orgs(client):
    _, token = await _new_user(client, "multi")
    a = (await _create(client, token, "ecommerce")).json()
    b = (await _create(client, token, "fintech")).json()
    r = await client.get(BASE, headers=H(token))
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 2
    ids = {o["id"] for o in data["items"]}
    assert a["id"] in ids and b["id"] in ids
    templates = {o["template"] for o in data["items"]}
    assert {"ecommerce", "fintech"} <= templates


# ============================== regenerate / reset ===================== #
async def test_regenerate_is_idempotent(client):
    _, token = await _new_user(client, "regen")
    created = (await _create(client, token, "saas")).json()
    org_id = created["id"]
    before = created["counts"]
    r = await client.post(f"{BASE}/{org_id}/regenerate", headers=H(token))
    assert r.status_code == 200, r.text
    after = r.json()["counts"]
    # Regeneration purges then reseeds -> identical counts, no duplication.
    assert after == before


async def test_reset_clears_data(client):
    _, token = await _new_user(client, "reset")
    created = (await _create(client, token, "healthcare")).json()
    org_id = created["id"]
    r = await client.post(f"{BASE}/{org_id}/reset", headers=H(token))
    assert r.status_code == 200, r.text
    for v in r.json()["counts"].values():
        assert v == 0


# ============================== delete ================================= #
async def test_delete_demo_org(client):
    _, token = await _new_user(client, "del")
    created = (await _create(client, token, "ecommerce")).json()
    org_id = created["id"]
    d = await client.delete(f"{BASE}/{org_id}", headers=H(token))
    assert d.status_code == 204
    listing = (await client.get(BASE, headers=H(token))).json()
    assert org_id not in {o["id"] for o in listing["items"]}


# ============================== ownership / isolation ================== #
async def test_non_owner_cannot_manage(client):
    _, owner = await _new_user(client, "owner")
    _, other = await _new_user(client, "other")
    created = (await _create(client, owner, "ecommerce")).json()
    org_id = created["id"]
    # The other user is not a member -> cannot regenerate or delete.
    assert (await client.post(f"{BASE}/{org_id}/regenerate", headers=H(other))).status_code == 403
    assert (await client.delete(f"{BASE}/{org_id}", headers=H(other))).status_code == 403
    # And it does not appear in their demo list.
    listing = (await client.get(BASE, headers=H(other))).json()
    assert org_id not in {o["id"] for o in listing["items"]}


# ============================== persisted data ========================= #
async def test_data_persisted_for_org(client):
    _, token = await _new_user(client, "persist")
    created = (await _create(client, token, "microservices")).json()
    org_id = created["id"]
    async with AsyncSessionLocal() as session:
        svc = (await session.execute(
            select(func.count()).select_from(Service).where(Service.organization_id == org_id)
        )).scalar()
        inc = (await session.execute(
            select(func.count()).select_from(IncidentInvestigation)
            .where(IncidentInvestigation.organization_id == org_id)
        )).scalar()
        linked = (await session.execute(
            select(func.count()).select_from(MonitoringAlert)
            .where(MonitoringAlert.organization_id == org_id, MonitoringAlert.incident_id.isnot(None))
        )).scalar()
    assert svc >= 6
    assert inc >= 2
    assert linked >= 2  # alerts linked to incidents (incident workflow)


# ============================== audit ================================== #
async def test_audit_logging(client):
    me, token = await _new_user(client, "audit")
    created = (await _create(client, token, "fintech")).json()
    await client.post(f"{BASE}/{created['id']}/regenerate", headers=H(token))
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(
                select(AuditLog.action).where(AuditLog.user_id == me["id"])
            )).scalars().all()
        )
    assert "demo_organization.create" in actions
    assert "demo_organization.regenerate" in actions
