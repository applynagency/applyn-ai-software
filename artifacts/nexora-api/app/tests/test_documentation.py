"""Tests for Sprint 51A - Product Documentation Center.

Covers default category seeding, article CRUD, slug uniqueness, search,
versioning (revisions + version bump), view tracking, navigation tree,
markdown/html/pdf export, rich media composition, validation, tenant
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
        "title": "Quickstart",
        "category_key": "getting-started",
        "content": "# Hello\n\nWelcome.",
        "summary": "Intro",
        "tags": ["intro"],
        **over,
    }
    return await client.post("/v1/docs/articles", headers=H(token), json=body)


# ============================== categories / nav ========================== #
async def test_navigation_seeds_default_categories(client):
    _, t = await create_authenticated_user(client, email="doc1@e.com", username="doc1")
    token = t["access_token"]
    nav = (await client.get("/v1/docs/navigation", headers=H(token))).json()
    keys = [c["key"] for c in nav["categories"]]
    assert "getting-started" in keys
    assert "api-reference" in keys
    assert "troubleshooting" in keys
    assert len(nav["categories"]) == 20
    # ordered by order_index
    assert keys[0] == "getting-started"


async def test_categories_endpoint(client):
    _, t = await create_authenticated_user(client, email="doc2@e.com", username="doc2")
    token = t["access_token"]
    cats = (await client.get("/v1/docs/categories", headers=H(token))).json()
    assert len(cats) == 20
    assert all("key" in c and "name" in c for c in cats)


# ============================== create / read ============================= #
async def test_create_and_get_article(client):
    _, t = await create_authenticated_user(client, email="doc3@e.com", username="doc3")
    token = t["access_token"]
    r = await _create(client, token)
    assert r.status_code == 201, r.text
    art = r.json()
    assert art["slug"] == "quickstart"
    assert art["version"] == 1
    assert art["content_html"]
    assert "getting-started" not in art["category_id"]  # resolved to a real id

    detail = (await client.get(f"/v1/docs/articles/{art['id']}", headers=H(token))).json()
    assert detail["title"] == "Quickstart"
    assert detail["tags"] == ["intro"]


async def test_create_requires_category(client):
    _, t = await create_authenticated_user(client, email="doc4@e.com", username="doc4")
    token = t["access_token"]
    r = await client.post("/v1/docs/articles", headers=H(token), json={"title": "X", "content": "y"})
    assert r.status_code == 400


async def test_invalid_status_rejected(client):
    _, t = await create_authenticated_user(client, email="doc5@e.com", username="doc5")
    token = t["access_token"]
    r = await _create(client, token, status="NOPE")
    assert r.status_code == 400


async def test_slug_uniqueness(client):
    _, t = await create_authenticated_user(client, email="doc6@e.com", username="doc6")
    token = t["access_token"]
    a = (await _create(client, token, title="Same Title")).json()
    b = (await _create(client, token, title="Same Title")).json()
    assert a["slug"] != b["slug"]
    assert b["slug"].startswith("same-title")


# ============================== list / search ============================= #
async def test_list_and_search(client):
    _, t = await create_authenticated_user(client, email="doc7@e.com", username="doc7")
    token = t["access_token"]
    await _create(client, token, title="Monitoring Guide", category_key="monitoring",
                  content="how to configure prometheus alerts")
    await _create(client, token, title="Cost Tips", category_key="cost-optimization",
                  content="reduce spend")

    allres = (await client.get("/v1/docs/articles", headers=H(token))).json()
    assert allres["total"] >= 2

    found = (await client.get("/v1/docs/articles?search=prometheus", headers=H(token))).json()
    titles = [a["title"] for a in found["items"]]
    assert "Monitoring Guide" in titles
    assert "Cost Tips" not in titles


async def test_list_filter_by_category(client):
    _, t = await create_authenticated_user(client, email="doc8@e.com", username="doc8")
    token = t["access_token"]
    await _create(client, token, title="Incident Runbook", category_key="incidents")
    res = (await client.get("/v1/docs/articles?category_key=incidents", headers=H(token))).json()
    assert res["total"] == 1
    assert res["items"][0]["title"] == "Incident Runbook"


# ============================== versioning =============================== #
async def test_update_creates_revision(client):
    _, t = await create_authenticated_user(client, email="doc9@e.com", username="doc9")
    token = t["access_token"]
    art = (await _create(client, token)).json()
    upd = (await client.put(f"/v1/docs/articles/{art['id']}", headers=H(token),
                            json={"content": "# Hello v2"})).json()
    assert upd["version"] == 2
    assert len(upd["revisions"]) == 1
    assert upd["revisions"][0]["version"] == 1


async def test_metadata_only_update_does_not_bump_version(client):
    _, t = await create_authenticated_user(client, email="doc10@e.com", username="doc10")
    token = t["access_token"]
    art = (await _create(client, token)).json()
    upd = (await client.put(f"/v1/docs/articles/{art['id']}", headers=H(token),
                            json={"tags": ["a", "b"]})).json()
    assert upd["version"] == 1
    assert upd["tags"] == ["a", "b"]


# ============================== views =================================== #
async def test_view_tracking(client):
    _, t = await create_authenticated_user(client, email="doc11@e.com", username="doc11")
    token = t["access_token"]
    art = (await _create(client, token)).json()
    one = (await client.get(f"/v1/docs/articles/{art['id']}", headers=H(token))).json()
    two = (await client.get(f"/v1/docs/articles/{art['id']}", headers=H(token))).json()
    assert two["view_count"] == one["view_count"] + 1
    # opting out does not increment
    no = (await client.get(f"/v1/docs/articles/{art['id']}?track_view=false", headers=H(token))).json()
    assert no["view_count"] == two["view_count"]


# ============================== rich media + export ====================== #
async def test_export_formats_and_rich_media(client):
    _, t = await create_authenticated_user(client, email="doc12@e.com", username="doc12")
    token = t["access_token"]
    art = (await _create(
        client, token,
        code_snippets=[{"language": "bash", "code": "curl localhost", "caption": "call"}],
        screenshots=[{"url": "https://x/y.png", "caption": "dashboard"}],
        videos=[{"url": "https://youtu.be/abc", "title": "demo", "provider": "youtube"}],
    )).json()

    md = await client.get(f"/v1/docs/articles/{art['id']}/export?format=markdown", headers=H(token))
    assert md.status_code == 200
    text = md.text
    assert "curl localhost" in text
    assert "y.png" in text
    assert "youtu.be/abc" in text

    html = await client.get(f"/v1/docs/articles/{art['id']}/export?format=html", headers=H(token))
    assert html.status_code == 200
    assert "<" in html.text

    pdf = await client.get(f"/v1/docs/articles/{art['id']}/export?format=pdf", headers=H(token))
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"


async def test_export_bad_format(client):
    _, t = await create_authenticated_user(client, email="doc13@e.com", username="doc13")
    token = t["access_token"]
    art = (await _create(client, token)).json()
    r = await client.get(f"/v1/docs/articles/{art['id']}/export?format=xls", headers=H(token))
    assert r.status_code == 400


# ============================== delete =================================== #
async def test_delete_article(client):
    _, t = await create_authenticated_user(client, email="doc14@e.com", username="doc14")
    token = t["access_token"]
    art = (await _create(client, token)).json()
    d = await client.delete(f"/v1/docs/articles/{art['id']}", headers=H(token))
    assert d.status_code == 204
    g = await client.get(f"/v1/docs/articles/{art['id']}", headers=H(token))
    assert g.status_code == 404


# ============================== isolation =============================== #
async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="docA@e.com", username="docA")
    _, t2 = await create_authenticated_user(client, email="docB@e.com", username="docB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    art = (await _create(client, tok1, title="Org1 Secret Doc")).json()
    assert (await client.get(f"/v1/docs/articles/{art['id']}", headers=H(tok2))).status_code == 404
    res = (await client.get("/v1/docs/articles", headers=H(tok2))).json()
    assert all(a["title"] != "Org1 Secret Doc" for a in res["items"])


# ============================== 404 ==================================== #
async def test_get_missing_article(client):
    _, t = await create_authenticated_user(client, email="doc15@e.com", username="doc15")
    token = t["access_token"]
    assert (await client.get("/v1/docs/articles/nope", headers=H(token))).status_code == 404


# ============================== audit ================================== #
async def test_audit_logging(client):
    me, t = await create_authenticated_user(client, email="doc16@e.com", username="doc16")
    token = t["access_token"]
    art = (await _create(client, token)).json()
    await client.get(f"/v1/docs/articles/{art['id']}", headers=H(token))
    await client.put(f"/v1/docs/articles/{art['id']}", headers=H(token), json={"content": "v2"})
    await client.get(f"/v1/docs/articles/{art['id']}/export?format=markdown", headers=H(token))
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert "documentation_article_created" in actions
    assert "documentation_article_viewed" in actions
    assert "documentation_article_updated" in actions
    assert "documentation_article_exported" in actions
