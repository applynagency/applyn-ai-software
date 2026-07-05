"""Tests for Sprint 51E - Customer Documentation Portal generator.

Covers route scanning, deterministic + idempotent generation into the 51A
Documentation Center, the portal index, PDF/HTML/Markdown manuals, guide/format
validation, integration with the docs list/search, tenant isolation and audit
logging. Strictly additive.
"""

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.services.documentation_generator import DocumentationGeneratorService
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers


# ============================== scanning ================================= #
def test_scan_routes_finds_real_endpoints():
    routes = DocumentationGeneratorService.scan_routes()
    paths = {(r["method"], r["path"]) for r in routes}
    assert ("POST", "/v1/docs/generate") in paths
    assert ("GET", "/v1/product-tours") in paths
    assert all(r["path"].startswith("/v1/") for r in routes)


def test_scan_navigation_and_modules():
    nav = DocumentationGeneratorService.scan_navigation()
    mods = DocumentationGeneratorService.scan_modules()
    assert any(n["module"] == "monitoring" for n in nav)
    assert all(n.get("nav_path") for n in nav)
    assert len(mods) == len(nav)


# ============================== generate ================================= #
async def test_generate_creates_articles(client):
    _, t = await create_authenticated_user(client, email="dg1@e.com", username="dg1")
    token = t["access_token"]
    r = await client.post("/v1/docs/generate", headers=H(token))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["articles_generated"] > 10
    assert body["created"] == body["articles_generated"]
    assert body["updated"] == 0
    assert body["routes_scanned"] > 20
    assert body["modules_scanned"] >= 1
    assert "API Guide" in body["guides"]


async def test_generate_is_idempotent(client):
    _, t = await create_authenticated_user(client, email="dg2@e.com", username="dg2")
    token = t["access_token"]
    first = (await client.post("/v1/docs/generate", headers=H(token))).json()
    second = (await client.post("/v1/docs/generate", headers=H(token))).json()
    assert second["created"] == 0
    assert second["updated"] == first["articles_generated"]
    # No duplicate articles created.
    listed = (await client.get("/v1/docs/articles?limit=200", headers=H(token))).json()
    assert listed["total"] == first["articles_generated"]


async def test_generated_articles_are_searchable(client):
    _, t = await create_authenticated_user(client, email="dg3@e.com", username="dg3")
    token = t["access_token"]
    await client.post("/v1/docs/generate", headers=H(token))
    found = (await client.get("/v1/docs/articles?search=Troubleshooting", headers=H(token))).json()
    assert any("Troubleshooting" in a["title"] for a in found["items"])
    api = (await client.get("/v1/docs/articles?category_key=api-reference", headers=H(token))).json()
    assert any(a["title"] == "API Guide" for a in api["items"])


# ============================== portal =================================== #
async def test_portal_index(client):
    _, t = await create_authenticated_user(client, email="dg4@e.com", username="dg4")
    token = t["access_token"]
    await client.post("/v1/docs/generate", headers=H(token))
    portal = (await client.get("/v1/docs/portal", headers=H(token))).json()
    assert portal["title"] == "Customer Documentation Portal"
    assert portal["generated_articles"] > 0
    assert portal["modules"] >= 1
    assert len(portal["navigation"]) == 20  # 51A categories
    guides = {g["key"]: g["article_count"] for g in portal["guides"]}
    assert guides["user"] >= 1
    assert guides["api"] == 1
    assert guides["troubleshooting"] == 1


# ============================== manuals ================================== #
async def test_manual_requires_generation_first(client):
    _, t = await create_authenticated_user(client, email="dg5@e.com", username="dg5")
    token = t["access_token"]
    r = await client.get("/v1/docs/manual?format=pdf", headers=H(token))
    assert r.status_code == 400


async def test_manual_formats_and_guides(client):
    _, t = await create_authenticated_user(client, email="dg6@e.com", username="dg6")
    token = t["access_token"]
    await client.post("/v1/docs/generate", headers=H(token))

    pdf = await client.get("/v1/docs/manual?guide=all&format=pdf", headers=H(token))
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"

    api_md = await client.get("/v1/docs/manual?guide=api&format=markdown", headers=H(token))
    assert api_md.status_code == 200
    assert "API Guide" in api_md.text
    assert "/v1/" in api_md.text

    user_html = await client.get("/v1/docs/manual?guide=user&format=html", headers=H(token))
    assert user_html.status_code == 200
    assert "<" in user_html.text

    bad_guide = await client.get("/v1/docs/manual?guide=nope", headers=H(token))
    assert bad_guide.status_code == 400
    bad_fmt = await client.get("/v1/docs/manual?guide=all&format=xls", headers=H(token))
    assert bad_fmt.status_code == 400


# ============================== isolation =============================== #
async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="dgA@e.com", username="dgA")
    _, t2 = await create_authenticated_user(client, email="dgB@e.com", username="dgB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    await client.post("/v1/docs/generate", headers=H(tok1))
    # org2 has no generated docs until they generate
    portal2 = (await client.get("/v1/docs/portal", headers=H(tok2))).json()
    assert portal2["generated_articles"] == 0
    manual2 = await client.get("/v1/docs/manual?format=pdf", headers=H(tok2))
    assert manual2.status_code == 400


# ===================== Sprint 52B — customer success ==================== #
async def _generate_and_list(client, token):
    await client.post("/v1/docs/generate", headers=H(token))
    listed = (await client.get("/v1/docs/articles?limit=200", headers=H(token))).json()
    return {a["slug"]: a for a in listed["items"]}


async def _article_by_slug(client, token, slug):
    by_slug = await _generate_and_list(client, token)
    aid = by_slug[slug]["id"]
    return (await client.get(f"/v1/docs/articles/{aid}", headers=H(token))).json()


async def test_quality_score_meets_target(client):
    _, t = await create_authenticated_user(client, email="cs1@e.com", username="cs1")
    body = (await client.post("/v1/docs/generate", headers=H(t["access_token"]))).json()
    assert body["quality_score"] >= 95
    assert body["quality"]["passes_target"] is True
    assert body["quality"]["modules_complete"] == body["quality"]["modules"]
    assert body["quality"]["incomplete_modules"] == {}


async def test_user_guide_has_twelve_sections(client):
    _, t = await create_authenticated_user(client, email="cs2@e.com", username="cs2")
    art = await _article_by_slug(client, t["access_token"], "user-guide-incidents")
    content = art["content"]
    for marker in [
        "## 1. What is this?",
        "## 2. Why do customers need this?",
        "## 3. Business value",
        "## 4. When should I use this?",
        "## 5. Step-by-step instructions",
        "## 6. Screenshots",
        "## 7. Expected result",
        "## 8. Common problems",
        "## 9. Troubleshooting",
        "## 10. Best practices",
        "## 11. Related features",
        "## 12. Next steps",
    ]:
        assert marker in content, marker


async def test_success_doc_guide_types(client):
    _, t = await create_authenticated_user(client, email="cs3@e.com", username="cs3")
    token = t["access_token"]
    await client.post("/v1/docs/generate", headers=H(token))
    guides = {g["key"]: g["article_count"] for g in (await client.get("/v1/docs/portal", headers=H(token))).json()["guides"]}
    for key in ["user", "use-case", "end-to-end", "runbook", "executive", "team-lead", "operations"]:
        assert guides.get(key, 0) >= 1, key


async def test_per_module_minimum_docs(client):
    _, t = await create_authenticated_user(client, email="cs4@e.com", username="cs4")
    by_slug = await _generate_and_list(client, t["access_token"])
    from app.services.documentation_generator import MODULE_CATALOG
    for m in MODULE_CATALOG:
        assert f"user-guide-{m['key']}" in by_slug
        assert f"use-case-{m['key']}" in by_slug
        assert f"end-to-end-{m['key']}" in by_slug


async def test_metadata_tags_present(client):
    _, t = await create_authenticated_user(client, email="cs5@e.com", username="cs5")
    by_slug = await _generate_and_list(client, t["access_token"])
    tags = by_slug["user-guide-incidents"]["tags"]
    assert any(x.startswith("role:") for x in tags)
    assert any(x.startswith("difficulty:") for x in tags)
    assert any(x.startswith("reading:") for x in tags)
    assert any(x.startswith("value:") for x in tags)


async def test_scenario_content(client):
    _, t = await create_authenticated_user(client, email="cs6@e.com", username="cs6")
    token = t["access_token"]
    incident = await _article_by_slug(client, token, "use-case-incidents")
    assert "checkout-service" in incident["content"]
    assert "Root Cause Analysis" in incident["content"]
    warroom = await _article_by_slug(client, token, "use-case-war-room")
    assert "Consensus" in warroom["content"]
    discovery = await _article_by_slug(client, token, "use-case-infrastructure-discovery")
    assert "Dependency" in discovery["content"] or "dependency" in discovery["content"]


# ============================== audit ================================== #
async def test_audit_logging(client):
    me, t = await create_authenticated_user(client, email="dg7@e.com", username="dg7")
    token = t["access_token"]
    await client.post("/v1/docs/generate", headers=H(token))
    await client.get("/v1/docs/manual?format=pdf", headers=H(token))
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert "documentation_generated" in actions
    assert "documentation_manual_exported" in actions
