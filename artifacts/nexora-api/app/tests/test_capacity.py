"""Tests for Sprint 43A — Capacity Planning & Forecasting.

Covers metric collection + persistence, the forecasting engine (7/30/90-day
projections, growth trend, saturation + exhaustion prediction), capacity
intelligence per resource, advisory recommendations (add nodes / increase
memory / increase storage / increase replicas / scale cluster), cost-impact
analysis, API (create/list/get/dashboard, pagination, error handling),
performance on large datasets, tenant isolation, and audit logging.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.tests.conftest import auth_headers, create_authenticated_user


def _now():
    return datetime.now(UTC)


def _series(resource_type, *, capacity, start_usage, per_day, days, service=None, cluster=None, unit=None):
    """Build a rising/flat sample series ending at 'now'."""
    now = _now()
    out = []
    for i in range(days):
        recorded = now - timedelta(days=(days - 1 - i))
        out.append({
            "resource_type": resource_type,
            "usage": start_usage + per_day * i,
            "capacity": capacity,
            "service": service,
            "cluster": cluster,
            "unit": unit,
            "recorded_at": recorded.isoformat(),
        })
    return out


async def _ingest(client, token, samples):
    return await client.post("/v1/capacity/metrics", headers=auth_headers(token), json={"samples": samples})


async def _forecast(client, token, **body):
    return await client.post("/v1/capacity/forecasts", headers=auth_headers(token), json=body)


# ============================== collection ================================= #
async def test_ingest_metrics_and_persist(client):
    _, tokens = await create_authenticated_user(client, email="cap1@e.com", username="cap1")
    token = tokens["access_token"]
    r = await _ingest(client, token, _series("CPU", capacity=100, start_usage=40, per_day=1, days=6))
    assert r.status_code == 201, r.text
    assert r.json()["ingested"] == 6


async def test_invalid_resource_type_rejected(client):
    _, tokens = await create_authenticated_user(client, email="cap2@e.com", username="cap2")
    token = tokens["access_token"]
    r = await _ingest(client, token, [{"resource_type": "QUANTUM", "usage": 1, "capacity": 10}])
    assert r.status_code == 400


# ============================== forecasting ================================ #
async def test_forecast_growth_and_exhaustion(client):
    _, tokens = await create_authenticated_user(client, email="cap3@e.com", username="cap3")
    token = tokens["access_token"]
    await _ingest(client, token, _series("CPU", capacity=100, start_usage=50, per_day=1.0, days=21, service="api"))
    r = await _forecast(client, token, resource_type="CPU", service="api", saturation_threshold=90)
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body) == 1
    f = body[0]
    assert f["forecast_7d"] < f["forecast_30d"] < f["forecast_90d"]
    assert f["trend"] == "GROWING"
    assert f["growth_rate_per_day"] > 0
    assert f["exhaustion_date"] is not None
    assert f["status"] in ("WARNING", "CRITICAL")
    assert f["recommendation_action"] == "SCALE_CLUSTER"  # CPU pressure
    assert f["recommendation"]


async def test_stable_resource_is_healthy_with_no_action(client):
    _, tokens = await create_authenticated_user(client, email="cap4@e.com", username="cap4")
    token = tokens["access_token"]
    await _ingest(client, token, _series("CPU", capacity=100, start_usage=50, per_day=0.0, days=10, service="flat"))
    f = (await _forecast(client, token, resource_type="CPU", service="flat")).json()[0]
    assert f["trend"] == "STABLE"
    assert f["status"] == "HEALTHY"
    assert f["recommendation_action"] == "NONE"
    assert f["exhaustion_date"] is None


async def test_forecast_all_resources_at_once(client):
    _, tokens = await create_authenticated_user(client, email="cap5@e.com", username="cap5")
    token = tokens["access_token"]
    await _ingest(client, token, _series("CPU", capacity=100, start_usage=50, per_day=1, days=10, service="api"))
    await _ingest(client, token, _series("MEMORY", capacity=64, start_usage=30, per_day=0.5, days=10, service="api"))
    await _ingest(client, token, _series("STORAGE", capacity=500, start_usage=200, per_day=5, days=10, service="api"))
    body = (await _forecast(client, token, service="api")).json()
    assert {f["resource_type"] for f in body} == {"CPU", "MEMORY", "STORAGE"}


async def test_recommendation_mapping_per_resource(client):
    _, tokens = await create_authenticated_user(client, email="cap6@e.com", username="cap6")
    token = tokens["access_token"]
    expected = {"MEMORY": "INCREASE_MEMORY", "STORAGE": "INCREASE_STORAGE",
                "NODE": "ADD_NODES", "POD": "INCREASE_REPLICAS"}
    for rt, action in expected.items():
        await _ingest(client, token, _series(rt, capacity=100, start_usage=60, per_day=2, days=15, service=f"svc-{rt}"))
        f = (await _forecast(client, token, resource_type=rt, service=f"svc-{rt}")).json()[0]
        assert f["recommendation_action"] == action, f"{rt} -> {f['recommendation_action']}"


# ============================== cost impact ================================ #
async def test_cost_impact_analysis(client):
    _, tokens = await create_authenticated_user(client, email="cap7@e.com", username="cap7")
    token = tokens["access_token"]
    await _ingest(client, token, _series("CPU", capacity=100, start_usage=50, per_day=1.0, days=21, service="api"))
    f = (await _forecast(client, token, resource_type="CPU", service="api")).json()[0]
    assert f["current_cost"] == 100 * 30  # capacity x unit cost
    assert f["projected_cost"] > f["current_cost"]
    assert f["delta_cost"] > 0


async def test_stable_cost_has_no_delta(client):
    _, tokens = await create_authenticated_user(client, email="cap8@e.com", username="cap8")
    token = tokens["access_token"]
    await _ingest(client, token, _series("STORAGE", capacity=500, start_usage=100, per_day=0.0, days=10, service="db"))
    f = (await _forecast(client, token, resource_type="STORAGE", service="db")).json()[0]
    assert f["delta_cost"] == 0


# ============================== API: list/get/pagination =================== #
async def test_list_pagination_and_get(client):
    _, tokens = await create_authenticated_user(client, email="cap9@e.com", username="cap9")
    token = tokens["access_token"]
    for rt in ("CPU", "MEMORY", "STORAGE"):
        await _ingest(client, token, _series(rt, capacity=100, start_usage=50, per_day=1, days=8, service="api"))
    await _forecast(client, token, service="api")  # creates 3

    page = (await client.get("/v1/capacity/forecasts?offset=0&limit=2", headers=auth_headers(token))).json()
    assert page["total"] >= 3
    assert len(page["items"]) == 2
    assert page["limit"] == 2

    fid = page["items"][0]["id"]
    one = await client.get(f"/v1/capacity/forecasts/{fid}", headers=auth_headers(token))
    assert one.status_code == 200 and one.json()["id"] == fid

    assert (await client.get("/v1/capacity/forecasts/nope", headers=auth_headers(token))).status_code == 404


async def test_create_forecast_without_metrics_errors(client):
    _, tokens = await create_authenticated_user(client, email="cap10@e.com", username="cap10")
    token = tokens["access_token"]
    r = await _forecast(client, token, resource_type="CPU")
    assert r.status_code == 400


# ============================== dashboard ================================== #
async def test_dashboard(client):
    _, tokens = await create_authenticated_user(client, email="cap11@e.com", username="cap11")
    token = tokens["access_token"]
    await _ingest(client, token, _series("CPU", capacity=100, start_usage=50, per_day=1.0, days=21, service="api"))
    await _ingest(client, token, _series("STORAGE", capacity=500, start_usage=100, per_day=0.0, days=10, service="db"))
    await _forecast(client, token, service="api")
    await _forecast(client, token, service="db")
    dash = (await client.get("/v1/capacity/dashboard", headers=auth_headers(token))).json()
    assert dash["total_forecasts"] >= 2
    assert dash["critical_count"] + dash["warning_count"] + dash["healthy_count"] == dash["total_forecasts"]
    assert dash["total_current_cost"] > 0
    assert len(dash["by_resource"]) >= 2


# ============================== performance ================================ #
async def test_large_dataset_performance(client):
    _, tokens = await create_authenticated_user(client, email="cap12@e.com", username="cap12")
    token = tokens["access_token"]
    # Multiple services + clusters: 3 x 2 x 50 = 300 samples.
    big = []
    for svc in ("a", "b", "c"):
        for cl in ("us", "eu"):
            big.extend(_series("CPU", capacity=100, start_usage=40, per_day=0.8, days=50, service=svc, cluster=cl))
    assert len(big) == 300
    r = await _ingest(client, token, big)
    assert r.status_code == 201 and r.json()["ingested"] == 300

    started = _now()
    body = (await _forecast(client, token, resource_type="CPU", service="a", cluster="us", lookback_days=60)).json()
    assert len(body) == 1 and body[0]["data_points"] == 50
    assert (_now() - started).total_seconds() < 10


# ============================== isolation ================================== #
async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="capA@e.com", username="capA")
    _, t2 = await create_authenticated_user(client, email="capB@e.com", username="capB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    await _ingest(client, tok1, _series("CPU", capacity=100, start_usage=50, per_day=1, days=8, service="api"))
    fid = (await _forecast(client, tok1, service="api")).json()[0]["id"]

    page = (await client.get("/v1/capacity/forecasts", headers=auth_headers(tok2))).json()
    assert page["total"] == 0
    assert (await client.get(f"/v1/capacity/forecasts/{fid}", headers=auth_headers(tok2))).status_code == 404
    # org B cannot generate a forecast from org A's metrics
    assert (await _forecast(client, tok2, resource_type="CPU", service="api")).status_code == 400


# ============================== audit ====================================== #
async def test_audit_events(client):
    me, tokens = await create_authenticated_user(client, email="cap13@e.com", username="cap13")
    token = tokens["access_token"]
    await _ingest(client, token, _series("CPU", capacity=100, start_usage=50, per_day=1, days=8, service="api"))
    fid = (await _forecast(client, token, service="api")).json()[0]["id"]
    await client.get(f"/v1/capacity/forecasts/{fid}", headers=auth_headers(token))
    await client.get("/v1/capacity/dashboard", headers=auth_headers(token))
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert {"capacity_metrics_ingested", "forecast_created", "forecast_viewed", "dashboard_viewed"} <= actions
