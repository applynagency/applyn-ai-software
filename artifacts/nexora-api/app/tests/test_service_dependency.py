"""Tests for Sprint 44B — Service Dependency Graph & Blast Radius Intelligence.

Covers dependency creation (and self/duplicate/unknown rejection), list/delete,
the graph endpoint, downstream/upstream traversal (direct + indirect),
circular-dependency handling, blast-radius calculation from an incident (origin
resolution + impacted dependents + customer impact), the blast-radius dashboard,
tenant isolation, and audit logging. All read-only.
"""

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.tests.conftest import auth_headers, create_authenticated_user


async def _service(client, token, name, tier="TIER_2"):
    r = await client.post("/v1/services", headers=auth_headers(token),
                          json={"name": name, "tier": tier})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _dep(client, token, src, tgt, dtype="SYNC"):
    return await client.post("/v1/service-dependencies", headers=auth_headers(token),
                             json={"source_service_id": src, "target_service_id": tgt,
                                   "dependency_type": dtype})


async def _team_agent(client, token):
    team = (await client.post("/v1/ai-teams", headers=auth_headers(token), json={"name": "Ops"})).json()
    await client.post("/v1/ai-team-agents", headers=auth_headers(token),
                      json={"team_id": team["id"], "name": "SRE", "role": "Ops", "instructions": "x",
                            "model": "claude-sonnet", "temperature": 0.2, "max_tokens": 300, "is_active": True})


async def _incident_for(client, token, service):
    await _team_agent(client, token)
    body = (await client.post("/v1/monitoring/poll", headers=auth_headers(token),
            json={"alerts": [{"provider": "PROMETHEUS", "alert_id": "a1", "alert_name": "HighErrorRate",
                              "severity": "CRITICAL", "service": service, "environment": "production"}]})).json()
    return body["alerts"][0]["incident_id"]


def _names(refs):
    return {r["name"] for r in refs}


# ============================== creation =================================== #
async def test_create_dependency(client):
    _, tokens = await create_authenticated_user(client, email="dep1@e.com", username="dep1")
    token = tokens["access_token"]
    a = await _service(client, token, "api")
    b = await _service(client, token, "db")
    r = await _dep(client, token, a, b, "DATASTORE")
    assert r.status_code == 201, r.text
    e = r.json()
    assert e["source_name"] == "api" and e["target_name"] == "db"
    assert e["dependency_type"] == "DATASTORE"


async def test_self_dependency_rejected(client):
    _, tokens = await create_authenticated_user(client, email="dep2@e.com", username="dep2")
    token = tokens["access_token"]
    a = await _service(client, token, "api")
    assert (await _dep(client, token, a, a)).status_code == 400


async def test_duplicate_rejected(client):
    _, tokens = await create_authenticated_user(client, email="dep3@e.com", username="dep3")
    token = tokens["access_token"]
    a = await _service(client, token, "api")
    b = await _service(client, token, "db")
    assert (await _dep(client, token, a, b)).status_code == 201
    assert (await _dep(client, token, a, b)).status_code == 409


async def test_unknown_service_rejected(client):
    _, tokens = await create_authenticated_user(client, email="dep4@e.com", username="dep4")
    token = tokens["access_token"]
    a = await _service(client, token, "api")
    assert (await _dep(client, token, a, "nope")).status_code == 404


# ============================== list / delete ============================== #
async def test_list_and_delete(client):
    _, tokens = await create_authenticated_user(client, email="dep5@e.com", username="dep5")
    token = tokens["access_token"]
    a = await _service(client, token, "api")
    b = await _service(client, token, "db")
    eid = (await _dep(client, token, a, b)).json()["id"]
    lst = (await client.get("/v1/service-dependencies", headers=auth_headers(token))).json()
    assert len(lst) == 1
    d = await client.delete(f"/v1/service-dependencies/{eid}", headers=auth_headers(token))
    assert d.status_code == 204
    assert len((await client.get("/v1/service-dependencies", headers=auth_headers(token))).json()) == 0


# ============================== traversal ================================== #
async def test_downstream_upstream_traversal(client):
    _, tokens = await create_authenticated_user(client, email="dep6@e.com", username="dep6")
    token = tokens["access_token"]
    a = await _service(client, token, "A")
    b = await _service(client, token, "B")
    c = await _service(client, token, "C")
    # A depends on B, B depends on C  (A -> B -> C)
    await _dep(client, token, a, b)
    await _dep(client, token, b, c)

    va = (await client.get(f"/v1/services/{a}/dependencies", headers=auth_headers(token))).json()
    assert _names(va["direct_dependencies"]) == {"B"}
    assert _names(va["indirect_dependencies"]) == {"C"}
    assert _names(va["downstream_services"]) == {"B", "C"}
    assert va["upstream_services"] == []
    assert va["has_cycle"] is False

    vc = (await client.get(f"/v1/services/{c}/dependencies", headers=auth_headers(token))).json()
    assert _names(vc["direct_dependents"]) == {"B"}
    assert _names(vc["indirect_dependents"]) == {"A"}
    assert _names(vc["upstream_services"]) == {"A", "B"}
    assert vc["downstream_services"] == []


async def test_circular_dependency_handling(client):
    _, tokens = await create_authenticated_user(client, email="dep7@e.com", username="dep7")
    token = tokens["access_token"]
    a = await _service(client, token, "A")
    b = await _service(client, token, "B")
    await _dep(client, token, a, b)
    await _dep(client, token, b, a)  # cycle A <-> B

    va = (await client.get(f"/v1/services/{a}/dependencies", headers=auth_headers(token))).json()
    assert va["has_cycle"] is True
    # Traversal terminates and excludes the start node.
    assert _names(va["downstream_services"]) == {"B"}
    assert _names(va["upstream_services"]) == {"B"}

    graph = (await client.get("/v1/service-dependencies/graph", headers=auth_headers(token))).json()
    assert len(graph["nodes"]) == 2 and len(graph["edges"]) == 2


# ============================== blast radius =============================== #
async def test_blast_radius_from_incident(client):
    _, tokens = await create_authenticated_user(client, email="dep8@e.com", username="dep8")
    token = tokens["access_token"]
    checkout = await _service(client, token, "checkout", tier="TIER_1")
    web = await _service(client, token, "web", tier="TIER_1")
    mobile = await _service(client, token, "mobile", tier="TIER_2")
    # web depends on checkout, mobile depends on web  → checkout failure impacts web + mobile
    await _dep(client, token, web, checkout)
    await _dep(client, token, mobile, web)

    incident_id = await _incident_for(client, token, "checkout")
    br = (await client.get(f"/v1/incidents/{incident_id}/blast-radius", headers=auth_headers(token))).json()
    assert br["origin_service_name"] == "checkout"
    assert br["resolved_from"] == "assignment"
    assert _names(br["direct_impact"]) == {"web"}
    assert _names(br["indirect_impact"]) == {"mobile"}
    assert _names(br["affected_services"]) == {"web", "mobile"}
    assert br["affected_count"] == 2
    assert br["customer_impact_level"] == "CRITICAL"  # tier-1 origin + critical sev + dependents
    assert br["tier_breakdown"].get("TIER_1", 0) >= 2


async def test_blast_radius_unmapped_service(client):
    _, tokens = await create_authenticated_user(client, email="dep9@e.com", username="dep9")
    token = tokens["access_token"]
    incident_id = await _incident_for(client, token, "ghost")  # not in catalog
    br = (await client.get(f"/v1/incidents/{incident_id}/blast-radius", headers=auth_headers(token))).json()
    assert br["origin_service_id"] is None
    assert br["customer_impact_level"] == "LOW"
    assert br["affected_count"] == 0


async def test_blast_radius_unknown_incident_404(client):
    _, tokens = await create_authenticated_user(client, email="dep10@e.com", username="dep10")
    token = tokens["access_token"]
    assert (await client.get("/v1/incidents/nope/blast-radius", headers=auth_headers(token))).status_code == 404


# ============================== dashboard ================================== #
async def test_blast_radius_dashboard(client):
    _, tokens = await create_authenticated_user(client, email="dep11@e.com", username="dep11")
    token = tokens["access_token"]
    a = await _service(client, token, "A")
    b = await _service(client, token, "B")
    c = await _service(client, token, "C")
    await _dep(client, token, a, b)  # A depends on B
    await _dep(client, token, b, c)  # B depends on C  → C has blast radius {A, B}
    dash = (await client.get("/v1/blast-radius/dashboard", headers=auth_headers(token))).json()
    assert dash["total_services"] == 3
    assert dash["total_dependencies"] == 2
    top = dash["highest_blast_radius"][0]
    assert top["service"]["name"] == "C"
    assert top["blast_radius_size"] == 2


# ============================== isolation ================================== #
async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="depA@e.com", username="depA")
    _, t2 = await create_authenticated_user(client, email="depB@e.com", username="depB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    a = await _service(client, tok1, "api")
    b = await _service(client, tok1, "db")
    eid = (await _dep(client, tok1, a, b)).json()["id"]

    assert (await client.get("/v1/service-dependencies", headers=auth_headers(tok2))).json() == []
    assert (await client.delete(f"/v1/service-dependencies/{eid}", headers=auth_headers(tok2))).status_code == 404
    assert (await client.get(f"/v1/services/{a}/dependencies", headers=auth_headers(tok2))).status_code == 404
    # org B cannot create a dependency referencing org A's services
    a2 = await _service(client, tok2, "api")
    assert (await _dep(client, tok2, a2, b)).status_code == 404


# ============================== audit ====================================== #
async def test_audit_events(client):
    me, tokens = await create_authenticated_user(client, email="dep12@e.com", username="dep12")
    token = tokens["access_token"]
    checkout = await _service(client, token, "checkout", tier="TIER_1")
    web = await _service(client, token, "web")
    await _dep(client, token, web, checkout)
    await client.get("/v1/service-dependencies/graph", headers=auth_headers(token))
    await client.get(f"/v1/services/{checkout}/dependencies", headers=auth_headers(token))
    await client.get("/v1/blast-radius/dashboard", headers=auth_headers(token))
    incident_id = await _incident_for(client, token, "checkout")
    await client.get(f"/v1/incidents/{incident_id}/blast-radius", headers=auth_headers(token))

    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert {"service_dependency_created", "dependency_graph_viewed", "service_dependencies_viewed",
            "blast_radius_dashboard_viewed", "blast_radius_viewed"} <= actions
