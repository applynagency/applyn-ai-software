"""Tests for Sprint 51C - Screenshot & Demo Asset Manager.

Covers asset CRUD, category/type validation, screenshot + video uploads,
module mapping, tagging, search/filter, the demo gallery grouping, tenant
isolation and audit logging. Strictly additive.
"""

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers


async def _create(client, token, **over):
    body = {
        "title": "Dashboard overview",
        "category": "DASHBOARD",
        "asset_type": "SCREENSHOT",
        "url": "https://cdn/x/dashboard.png",
        "module": "dashboard",
        "description": "Main dashboard",
        "tags": ["overview", "ui"],
        **over,
    }
    return await client.post("/v1/demo-assets", headers=H(token), json=body)


# ============================== create / read ============================= #
async def test_create_screenshot(client):
    _, t = await create_authenticated_user(client, email="da1@e.com", username="da1")
    token = t["access_token"]
    r = await _create(client, token)
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["category"] == "DASHBOARD"
    assert a["asset_type"] == "SCREENSHOT"
    assert a["tags"] == ["overview", "ui"]


async def test_create_video(client):
    _, t = await create_authenticated_user(client, email="da2@e.com", username="da2")
    token = t["access_token"]
    a = (await _create(client, token, title="War room demo", category="WAR_ROOM",
                       asset_type="VIDEO", url="https://cdn/v/warroom.mp4",
                       duration_seconds=95, module="war-room")).json()
    assert a["asset_type"] == "VIDEO"
    assert a["duration_seconds"] == 95


async def test_invalid_category(client):
    _, t = await create_authenticated_user(client, email="da3@e.com", username="da3")
    token = t["access_token"]
    r = await _create(client, token, category="NOPE")
    assert r.status_code == 400


async def test_invalid_type(client):
    _, t = await create_authenticated_user(client, email="da4@e.com", username="da4")
    token = t["access_token"]
    r = await _create(client, token, asset_type="GIF")
    assert r.status_code == 400


async def test_get_and_404(client):
    _, t = await create_authenticated_user(client, email="da5@e.com", username="da5")
    token = t["access_token"]
    a = (await _create(client, token)).json()
    got = (await client.get(f"/v1/demo-assets/{a['id']}", headers=H(token))).json()
    assert got["id"] == a["id"]
    assert (await client.get("/v1/demo-assets/nope", headers=H(token))).status_code == 404


# ============================== list / filter ============================ #
async def test_list_filter_and_search(client):
    _, t = await create_authenticated_user(client, email="da6@e.com", username="da6")
    token = t["access_token"]
    await _create(client, token, title="Monitoring view", category="MONITORING",
                  module="monitoring", tags=["alerts"])
    await _create(client, token, title="Cost view", category="COST", module="cost", tags=["spend"])

    by_cat = (await client.get("/v1/demo-assets?category=MONITORING", headers=H(token))).json()
    assert all(a["category"] == "MONITORING" for a in by_cat)

    by_module = (await client.get("/v1/demo-assets?module=cost", headers=H(token))).json()
    assert all(a["module"] == "cost" for a in by_module)

    by_tag = (await client.get("/v1/demo-assets?tag=alerts", headers=H(token))).json()
    assert any(a["title"] == "Monitoring view" for a in by_tag)
    assert all("alerts" in a["tags"] for a in by_tag)

    found = (await client.get("/v1/demo-assets?search=Cost", headers=H(token))).json()
    assert any(a["title"] == "Cost view" for a in found)


async def test_filter_by_type(client):
    _, t = await create_authenticated_user(client, email="da7@e.com", username="da7")
    token = t["access_token"]
    await _create(client, token, asset_type="SCREENSHOT", url="https://cdn/s.png")
    await _create(client, token, asset_type="VIDEO", url="https://cdn/v.mp4")
    vids = (await client.get("/v1/demo-assets?asset_type=VIDEO", headers=H(token))).json()
    assert all(a["asset_type"] == "VIDEO" for a in vids)


# ============================== gallery ================================= #
async def test_gallery_grouping(client):
    _, t = await create_authenticated_user(client, email="da8@e.com", username="da8")
    token = t["access_token"]
    await _create(client, token, category="DASHBOARD", url="https://cdn/1.png")
    await _create(client, token, category="DASHBOARD", url="https://cdn/2.png")
    await _create(client, token, category="AI_COPILOT", url="https://cdn/3.png")

    gal = (await client.get("/v1/demo-assets/gallery", headers=H(token))).json()
    assert gal["total_assets"] == 3
    cats = {s["category"]: s["count"] for s in gal["sections"]}
    assert cats["DASHBOARD"] == 2
    assert cats["AI_COPILOT"] == 1
    # spec category order: DASHBOARD precedes AI_COPILOT
    order = [s["category"] for s in gal["sections"]]
    assert order.index("DASHBOARD") < order.index("AI_COPILOT")


# ============================== delete ================================= #
async def test_delete(client):
    _, t = await create_authenticated_user(client, email="da9@e.com", username="da9")
    token = t["access_token"]
    a = (await _create(client, token)).json()
    d = await client.delete(f"/v1/demo-assets/{a['id']}", headers=H(token))
    assert d.status_code == 204
    assert (await client.get(f"/v1/demo-assets/{a['id']}", headers=H(token))).status_code == 404


# ============================== isolation =============================== #
async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="daA@e.com", username="daA")
    _, t2 = await create_authenticated_user(client, email="daB@e.com", username="daB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    a = (await _create(client, tok1, title="Org1 asset")).json()
    assert (await client.get(f"/v1/demo-assets/{a['id']}", headers=H(tok2))).status_code == 404
    assert (await client.get("/v1/demo-assets", headers=H(tok2))).json() == []
    assert (await client.delete(f"/v1/demo-assets/{a['id']}", headers=H(tok2))).status_code == 404


# ============================== audit ================================== #
async def test_audit_logging(client):
    me, t = await create_authenticated_user(client, email="da10@e.com", username="da10")
    token = t["access_token"]
    a = (await _create(client, token)).json()
    await client.delete(f"/v1/demo-assets/{a['id']}", headers=H(token))
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert "demo_asset_created" in actions
    assert "demo_asset_deleted" in actions
