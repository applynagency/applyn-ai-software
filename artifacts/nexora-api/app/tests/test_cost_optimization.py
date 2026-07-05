"""Tests for Sprint 43B — Cost Optimization Intelligence.

Covers the cost intelligence engine (current cost, estimated waste, potential
savings, optimization score), idle-resource detection, over-provisioning /
rightsizing recommendations, non-production scheduling, savings calculations,
cost forecasting (30/90/365-day), optimization score + levels, cost-trend
analysis with anomalies, cost breakdown by service/environment, the API
(analyze/list/get/dashboard, pagination, error handling), tenant isolation,
audit logging, and no-secret-leakage.

These are read-only, advisory analytics — nothing scales or mutates infra.
"""

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.tests.conftest import auth_headers, create_authenticated_user


def _now():
    return datetime.now(UTC)


def _series(resource_type, *, capacity, start_usage, per_day, days,
            service=None, cluster=None, environment=None, unit=None):
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
            "environment": environment,
            "unit": unit,
            "recorded_at": recorded.isoformat(),
        })
    return out


async def _ingest(client, token, samples):
    return await client.post("/v1/capacity/metrics", headers=auth_headers(token), json={"samples": samples})


async def _analyze(client, token, **body):
    return await client.post("/v1/cost-optimization/analyze", headers=auth_headers(token), json=body)


# ============================== idle detection ============================= #
async def test_idle_resource_detection(client):
    _, tokens = await create_authenticated_user(client, email="co1@e.com", username="cost1")
    token = tokens["access_token"]
    # 10 nodes, ~2% utilized → idle, full spend is waste.
    await _ingest(client, token, _series("NODE", capacity=10, start_usage=0.2, per_day=0.0, days=10, service="ghost"))
    r = await _analyze(client, token, service="ghost")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["idle_count"] >= 1
    assert body["current_cost"] == 10 * 200  # 10 nodes x $200
    assert body["estimated_waste"] == body["current_cost"]
    kinds = {rec["kind"] for rec in body["recommendations"]}
    assert "IDLE_RESOURCE" in kinds
    # idle → critical waste
    assert body["optimization_score"] == 0
    assert body["optimization_level"] == "CRITICAL_WASTE"


# ============================== over-provisioning ========================== #
async def test_overprovisioning_and_rightsizing(client):
    _, tokens = await create_authenticated_user(client, email="co2@e.com", username="cost2")
    token = tokens["access_token"]
    # CPU 100 vCPU, ~10% utilized → over-provisioned, rightsize down.
    await _ingest(client, token, _series("CPU", capacity=100, start_usage=10, per_day=0.0, days=10, service="api"))
    body = (await _analyze(client, token, service="api")).json()
    assert body["overprovisioned_count"] >= 1
    rec = next(r for r in body["recommendations"] if r["kind"] == "OVERPROVISIONED")
    assert rec["monthly_savings"] > 0
    assert rec["projected_cost"] < rec["current_cost"]
    assert "advisory" in rec["action"].lower()
    assert body["potential_savings"] > 0


async def test_efficient_resource_has_no_recommendations(client):
    _, tokens = await create_authenticated_user(client, email="co3@e.com", username="cost3")
    token = tokens["access_token"]
    # CPU 65% utilized → efficient.
    await _ingest(client, token, _series("CPU", capacity=100, start_usage=65, per_day=0.0, days=10, service="api"))
    body = (await _analyze(client, token, service="api")).json()
    assert body["idle_count"] == 0
    assert body["overprovisioned_count"] == 0
    assert body["estimated_waste"] == 0
    assert body["optimization_score"] == 100
    assert body["optimization_level"] == "EXCELLENT"


# ============================== non-prod scheduling ======================== #
async def test_nonprod_scheduling_recommendation(client):
    _, tokens = await create_authenticated_user(client, email="co4@e.com", username="cost4")
    token = tokens["access_token"]
    # Efficiently used but in staging → scheduling opportunity, no resource waste.
    await _ingest(client, token, _series("CPU", capacity=100, start_usage=65, per_day=0.0, days=10,
                                         service="api", environment="staging"))
    body = (await _analyze(client, token, environment="staging")).json()
    assert body["nonprod_count"] >= 1
    sched = next(r for r in body["recommendations"] if r["kind"] == "NON_PROD_SCHEDULE")
    assert sched["monthly_savings"] > 0
    # Score reflects utilization efficiency (no waste), but savings still exist.
    assert body["estimated_waste"] == 0
    assert body["optimization_score"] == 100
    assert body["potential_savings"] > 0


# ============================== savings math =============================== #
async def test_savings_calculations_consistent(client):
    _, tokens = await create_authenticated_user(client, email="co5@e.com", username="cost5")
    token = tokens["access_token"]
    await _ingest(client, token, _series("NODE", capacity=8, start_usage=0.1, per_day=0.0, days=8, service="idle-svc"))
    body = (await _analyze(client, token, service="idle-svc")).json()
    assert abs(body["annual_savings"] - body["potential_savings"] * 12) < 0.5
    assert abs(body["optimized_cost"] - (body["current_cost"] - body["potential_savings"])) < 0.5
    assert 0 <= body["savings_percentage"] <= 100


# ============================== forecasting ================================ #
async def test_cost_forecast_growth(client):
    _, tokens = await create_authenticated_user(client, email="co6@e.com", username="cost6")
    token = tokens["access_token"]
    # Growing-but-efficient CPU: usage 50→79 over 30d, needs more capacity later.
    await _ingest(client, token, _series("CPU", capacity=100, start_usage=50, per_day=1.0, days=30, service="api"))
    body = (await _analyze(client, token, service="api", lookback_days=45)).json()
    assert body["forecast_30d"] >= body["current_cost"]
    assert body["forecast_90d"] >= body["forecast_30d"]
    assert body["forecast_365d"] >= body["forecast_90d"]


# ============================== trend + anomaly ============================ #
async def test_cost_trend_and_anomaly(client):
    _, tokens = await create_authenticated_user(client, email="co7@e.com", username="cost7")
    token = tokens["access_token"]
    now = _now()
    samples = []
    for i in range(56):  # 8 weeks of daily samples
        recorded = now - timedelta(days=(55 - i))
        # last 7 days spike from ~50 to ~250
        usage = 250 if i >= 49 else 50
        samples.append({
            "resource_type": "CPU", "usage": usage, "capacity": 400,
            "service": "api", "recorded_at": recorded.isoformat(),
        })
    await _ingest(client, token, samples)
    body = (await _analyze(client, token, service="api", lookback_days=90)).json()
    assert len(body["weekly_trend"]) >= 3
    assert any(p["anomaly"] for p in body["weekly_trend"])


# ============================== breakdown ================================== #
async def test_cost_breakdown_by_service_and_env(client):
    _, tokens = await create_authenticated_user(client, email="co8@e.com", username="cost8")
    token = tokens["access_token"]
    await _ingest(client, token, _series("CPU", capacity=50, start_usage=30, per_day=0.0, days=6,
                                         service="web", environment="prod"))
    await _ingest(client, token, _series("MEMORY", capacity=64, start_usage=40, per_day=0.0, days=6,
                                         service="db", environment="prod"))
    body = (await _analyze(client, token)).json()
    svc_names = {c["name"] for c in body["cost_by_service"]}
    env_names = {c["name"] for c in body["cost_by_environment"]}
    assert {"web", "db"} <= svc_names
    assert "prod" in env_names


# ============================== API: list/get/pagination =================== #
async def test_analyze_list_get_pagination(client):
    _, tokens = await create_authenticated_user(client, email="co9@e.com", username="cost9")
    token = tokens["access_token"]
    await _ingest(client, token, _series("CPU", capacity=100, start_usage=10, per_day=0.0, days=8, service="api"))
    a1 = (await _analyze(client, token, service="api")).json()
    await _analyze(client, token, service="api")

    page = (await client.get("/v1/cost-optimization/analyses?offset=0&limit=1", headers=auth_headers(token))).json()
    assert page["total"] >= 2
    assert len(page["items"]) == 1
    assert page["limit"] == 1

    one = await client.get(f"/v1/cost-optimization/analyses/{a1['id']}", headers=auth_headers(token))
    assert one.status_code == 200 and one.json()["id"] == a1["id"]
    assert one.json()["recommendations"]  # full report rehydrated

    assert (await client.get("/v1/cost-optimization/analyses/nope", headers=auth_headers(token))).status_code == 404


async def test_analyze_without_metrics_errors(client):
    _, tokens = await create_authenticated_user(client, email="co10@e.com", username="cost10")
    token = tokens["access_token"]
    r = await _analyze(client, token, service="nothing")
    assert r.status_code == 400


# ============================== dashboard ================================== #
async def test_dashboard(client):
    _, tokens = await create_authenticated_user(client, email="co11@e.com", username="cost11")
    token = tokens["access_token"]
    # empty first
    empty = (await client.get("/v1/cost-optimization/dashboard", headers=auth_headers(token))).json()
    assert empty["has_data"] is False

    await _ingest(client, token, _series("NODE", capacity=10, start_usage=0.2, per_day=0.0, days=8, service="ghost"))
    await _analyze(client, token, service="ghost")
    dash = (await client.get("/v1/cost-optimization/dashboard", headers=auth_headers(token))).json()
    assert dash["has_data"] is True
    assert dash["current_cost"] > 0
    assert dash["potential_savings"] > 0
    assert dash["optimization_level"] in ("EXCELLENT", "GOOD", "NEEDS_IMPROVEMENT", "CRITICAL_WASTE")
    assert len(dash["top_recommendations"]) >= 1


# ============================== isolation ================================== #
async def test_tenant_isolation(client):
    _, t1 = await create_authenticated_user(client, email="coA@e.com", username="costA")
    _, t2 = await create_authenticated_user(client, email="coB@e.com", username="costB")
    tok1, tok2 = t1["access_token"], t2["access_token"]
    await _ingest(client, tok1, _series("CPU", capacity=100, start_usage=10, per_day=0.0, days=8, service="api"))
    aid = (await _analyze(client, tok1, service="api")).json()["id"]

    page = (await client.get("/v1/cost-optimization/analyses", headers=auth_headers(tok2))).json()
    assert page["total"] == 0
    assert (await client.get(f"/v1/cost-optimization/analyses/{aid}", headers=auth_headers(tok2))).status_code == 404
    # org B cannot analyze org A's metrics
    assert (await _analyze(client, tok2, service="api")).status_code == 400


# ============================== audit ====================================== #
async def test_audit_events(client):
    me, tokens = await create_authenticated_user(client, email="co12@e.com", username="cost12")
    token = tokens["access_token"]
    await _ingest(client, token, _series("CPU", capacity=100, start_usage=10, per_day=0.0, days=8, service="api"))
    aid = (await _analyze(client, token, service="api")).json()["id"]
    await client.get(f"/v1/cost-optimization/analyses/{aid}", headers=auth_headers(token))
    await client.get("/v1/cost-optimization/dashboard", headers=auth_headers(token))
    async with AsyncSessionLocal() as session:
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.user_id == me["id"]))).scalars().all()
        )
    assert {"cost_analysis_created", "cost_analysis_viewed", "cost_dashboard_viewed"} <= actions


# ============================== no secret leakage ========================== #
async def test_no_secret_leakage(client):
    _, tokens = await create_authenticated_user(client, email="co13@e.com", username="cost13")
    token = tokens["access_token"]
    await _ingest(client, token, _series("CPU", capacity=100, start_usage=10, per_day=0.0, days=8, service="api"))
    body = (await _analyze(client, token, service="api")).json()
    blob = json.dumps(body).lower()
    for bad in ("password", "secret", "api_key", "apikey", "token", "credential"):
        assert bad not in blob
