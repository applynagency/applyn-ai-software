"""Tests for Sprint 46B - Architecture Discovery & Service Map Engine.

Covers node discovery + typing (service / database / load balancer / k8s / cloud
/ repository), edge construction from dependencies, monitoring-only service
discovery, and detection of orphans, single points of failure, missing
monitoring, and missing SLO coverage. Plus list/get/dashboard, tenant isolation,
audit logging. Read-only.
"""

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.services.architecture import _classify
from app.tests.conftest import auth_headers, create_authenticated_user

H = auth_headers


async def _service(client, token, name, tier="TIER_2"):
    return (await client.post("/v1/services", headers=H(token),
                              json={"name": name, "tier": tier, "owner_team": "core"})).json()


async def _slo(client, token, sid):
    return await client.post(f"/v1/services/{sid}/slos", headers=H(token),
                             json={"name": "a", "slo_type": "AVAILABILITY",
                                   "target_percentage": 99.9, "window_days": 30})


async def _dep(client, token, src, tgt, dtype="SYNC"):
    return await client.post("/v1/service-dependencies", headers=H(token),
                             json={"source_service_id": src, "target_service_id": tgt,
                                   "dependency_type": dtype})


async def _alert(client, token, name, service, provider="PROMETHEUS", env="production"):
    return await client.post("/v1/monitoring/poll", headers=H(token), json={"alerts": [
        {"provider": provider, "alert_id": f"a-{name}-{service}", "alert_name": name,
         "severity": "WARNING", "service": service, "environment": env}]})


async def _discover(client, token):
    return await client.post("/v1/architecture/discover", headers=H(token))


def _by_name(nodes, name):
    return next((n for n in nodes if n["name"] == name), None)


# ============================== classification =========================== #
def test_classify_node_types():
    assert _classify("checkout") == "SERVICE"
    assert _classify("orders-db") == "DATABASE"
    assert _classify("user-postgres") == "DATABASE"
    assert _classify("session-redis") == "DATABASE"
    assert _classify("api-gateway") == "LOAD_BALANCER"
    assert _classify("edge-nginx") == "LOAD_BALANCER"
    assert _classify("ingress-controller") == "LOAD_BALANCER"


# ============================== discovery ================================ #
async def test_discover_builds_typed_nodes(client):
    _, t = await create_authenticated_user(client, email="ar1@e.com", username="ar1")
    token = t["access_token"]
    await _service(client, token, "checkout")
    await _service(client, token, "orders-db")
    await _service(client, token, "api-gateway")
    r = await _discover(client, token)
    assert r.status_code == 201, r.text
    snap = r.json()
    types = {n["name"]: n["node_type"] for n in snap["nodes"]}
    assert types["checkout"] == "SERVICE"
    assert types["orders-db"] == "DATABASE"
    assert types["api-gateway"] == "LOAD_BALANCER"
    assert snap["node_type_counts"]["DATABASE"] == 1
    assert snap["node_count"] == 3


async def test_dependencies_become_edges_and_spof(client):
    _, t = await create_authenticated_user(client, email="ar2@e.com", username="ar2")
    token = t["access_token"]
    a = await _service(client, token, "checkout")
    b = await _service(client, token, "search")
    db = await _service(client, token, "orders-db")
    await _dep(client, token, a["id"], db["id"], "DATASTORE")
    await _dep(client, token, b["id"], db["id"], "DATASTORE")
    snap = (await _discover(client, token)).json()
    assert snap["edge_count"] == 2
    assert any(e["relationship"] == "STORES_IN" for e in snap["edges"])
    db_node = _by_name(snap["nodes"], "orders-db")
    assert db_node["dependents_count"] == 2
    assert db_node["is_spof"] is True
    assert "orders-db" in snap["risk_areas"]["single_points_of_failure"]


async def test_orphan_detection(client):
    _, t = await create_authenticated_user(client, email="ar3@e.com", username="ar3")
    token = t["access_token"]
    await _service(client, token, "lonely")
    a = await _service(client, token, "checkout")
    b = await _service(client, token, "payments")
    await _dep(client, token, a["id"], b["id"])
    snap = (await _discover(client, token)).json()
    assert "lonely" in snap["risk_areas"]["orphan_services"]
    assert "checkout" not in snap["risk_areas"]["orphan_services"]
    assert _by_name(snap["nodes"], "lonely")["is_orphan"] is True


async def test_missing_monitoring_and_slo(client):
    _, t = await create_authenticated_user(client, email="ar4@e.com", username="ar4")
    token = t["access_token"]
    a = await _service(client, token, "checkout")
    await _service(client, token, "payments")
    await _slo(client, token, a["id"])           # checkout has SLO
    await _alert(client, token, "cpu", "checkout")  # checkout has monitoring
    snap = (await _discover(client, token)).json()
    rk = snap["risk_areas"]
    # checkout is covered
    assert "checkout" not in rk["missing_monitoring"]
    assert "checkout" not in rk["missing_slo"]
    # payments is missing both
    assert "payments" in rk["missing_monitoring"]
    assert "payments" in rk["missing_slo"]
    chk = _by_name(snap["nodes"], "checkout")
    assert chk["has_monitoring"] and chk["has_slo"]


async def test_infra_discovery_k8s_cloud(client):
    _, t = await create_authenticated_user(client, email="ar5@e.com", username="ar5")
    token = t["access_token"]
    await _service(client, token, "checkout")
    # cloud resource discovered from a cloud monitoring provider
    await _alert(client, token, "ec2", "checkout", provider="AWS")
    # kubernetes workload discovered from capacity metrics (cluster set)
    await client.post("/v1/capacity/metrics", headers=H(token), json={"samples": [
        {"resource_type": "CPU", "usage": 4, "capacity": 10, "cluster": "prod-eks",
         "service": "checkout", "environment": "production"}]})
    snap = (await _discover(client, token)).json()
    types = {n["node_type"] for n in snap["nodes"]}
    assert "KUBERNETES_WORKLOAD" in types
    assert "CLOUD_RESOURCE" in types
    # checkout runs-on both infra nodes
    runs = [e for e in snap["edges"] if e["relationship"] == "RUNS_ON"]
    assert len(runs) >= 2


async def test_monitoring_only_service_discovered(client):
    _, t = await create_authenticated_user(client, email="ar6@e.com", username="ar6")
    token = t["access_token"]
    # no catalog service; only an alert mentions "ghost"
    await _alert(client, token, "err", "ghost")
    snap = (await _discover(client, token)).json()
    ghost = _by_name(snap["nodes"], "ghost")
    assert ghost is not None and ghost["has_monitoring"] is True


# ============================== list / get / dashboard =================== #
async def test_list_get_dashboard(client):
    _, t = await create_authenticated_user(client, email="ar7@e.com", username="ar7")
    token = t["access_token"]
    await _service(client, token, "checkout")
    snap = (await _discover(client, token)).json()
    lst = (await client.get("/v1/architecture", headers=H(token))).json()
    assert len(lst) == 1 and lst[0]["id"] == snap["id"]
    got = (await client.get(f"/v1/architecture/{snap['id']}", headers=H(token))).json()
    assert got["id"] == snap["id"] and got["nodes"]
    assert (await client.get("/v1/architecture/nope", headers=H(token))).status_code == 404
    await _discover(client, token)
    dash = (await client.get("/v1/architecture/dashboard", headers=H(token))).json()
    assert dash["snapshots_count"] == 2 and len(dash["trend"]) == 2
    assert dash["latest"] is not None


# ============================== isolation ================================ #
async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="arA@e.com", username="arA")
    _, t2 = await create_authenticated_user(client, email="arB@e.com", username="arB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    await _service(client, tok1, "checkout")
    snap = (await _discover(client, tok1)).json()
    assert (await client.get("/v1/architecture", headers=H(tok2))).json() == []
    assert (await client.get(f"/v1/architecture/{snap['id']}", headers=H(tok2))).status_code == 404
    d2 = (await client.get("/v1/architecture/dashboard", headers=H(tok2))).json()
    assert d2["snapshots_count"] == 0


# ============================== audit ==================================== #
async def test_audit_logging(client):
    me, t = await create_authenticated_user(client, email="ar8@e.com", username="ar8")
    token = t["access_token"]
    await _discover(client, token)
    await client.get("/v1/architecture/dashboard", headers=H(token))
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert {"architecture_discovered", "architecture_dashboard_viewed"} <= actions
