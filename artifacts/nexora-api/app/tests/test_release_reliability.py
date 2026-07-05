"""Sprint 65F — Release Reliability tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.release_reliability.health_gates import (
    GATE_FAIL,
    GATE_INSUFFICIENT,
    GATE_PASS,
    evaluate_health_gate,
)
from app.release_reliability.promotion import evaluate_promotion, is_freeze_active
from app.release_reliability.rollback import recommend_rollback
from app.release_reliability.rollout import detect_provider_mode, propose_rollout
from app.tests.conftest import auth_headers, create_authenticated_user


def test_health_gate_pass():
    gate = evaluate_health_gate(
        {"pod_ready": True, "rollout_status": "Complete", "error_rate": 0.01, "security_gate": "PASS"},
        environment_tier="STAGING",
    )
    assert gate["decision"] == GATE_PASS


def test_health_gate_insufficient_evidence():
    gate = evaluate_health_gate({}, environment_tier="PRODUCTION", is_production=True)
    assert gate["decision"] == GATE_INSUFFICIENT
    assert gate["blocks_promotion"] is True


def test_health_gate_fail_on_error_rate():
    gate = evaluate_health_gate(
        {"pod_ready": True, "rollout_status": "Complete", "error_rate": 0.5},
    )
    assert gate["decision"] == GATE_FAIL


def test_production_warn_becomes_fail():
    gate = evaluate_health_gate(
        {"pod_ready": True, "rollout_status": "Complete", "error_rate": 0.01, "latency_p99_ms": 5000},
        is_production=True,
    )
    assert gate["decision"] == GATE_FAIL


def test_provider_mode_offline():
    assert detect_provider_mode("argo_rollouts", configured=True) == "offline"
    assert detect_provider_mode("argo_rollouts", configured=False) == "unavailable"
    assert detect_provider_mode("argo_rollouts", configured=True, secret={"endpoint": "https://argo"}) == "live"


def test_rollout_simulated_label():
    state = propose_rollout(provider_type="k8s_rolling", strategy="canary", target="app", mode="offline")
    assert state["simulated"] is True


def test_promotion_blocked_insufficient_evidence():
    result = evaluate_promotion(
        source_verification="INSUFFICIENT_EVIDENCE",
        security_gate="PASS",
        artifact_digest="sha256:abc",
        existing_digest="sha256:abc",
        policy={"requires_verification": True, "requires_security_gate": True,
                "requires_approval": True, "digest_immutable": True},
        freeze_active=False,
        environment_tier="PRODUCTION",
    )
    assert result["allowed"] is False
    assert "insufficient_verification_evidence" in result["block_reasons"]


def test_freeze_window_blocks():
    now = datetime.now(UTC)
    assert is_freeze_active(
        [{"active": True, "environment_tier": "PRODUCTION",
          "starts_at": now - timedelta(hours=1), "ends_at": now + timedelta(hours=1)}],
        tier="PRODUCTION",
    ) is True


def test_rollback_recommendation_requires_approval():
    rec = recommend_rollback(health_gate_decision="FAIL", environment_tier="PRODUCTION")
    assert rec["requires_approval"] is True
    assert rec["automatic"] is False


def test_rollback_never_automatic_by_default():
    rec = recommend_rollback(health_gate_decision="FAIL", environment_tier="PRODUCTION", auto_rollback_policy=True)
    assert rec["automatic"] is False


@pytest.mark.asyncio
async def test_release_reliability_api_flow(client):
    _, tokens = await create_authenticated_user(client, email="rr1@e.com", username="rruser1")
    headers = auth_headers(tokens["access_token"])

    envs = await client.get("/v1/delivery/environments", headers=headers)
    assert envs.status_code == 200
    env_id = envs.json()[0]["id"]

    rel = await client.post(
        "/v1/delivery/releases", headers=headers,
        json={"version": "1.2.0", "environment_id": env_id, "release_notes": "Test"},
    )
    assert rel.status_code == 201
    release_id = rel.json()["id"]

    rr = await client.post(
        "/v1/delivery/release-reliability", headers=headers,
        json={"release_id": release_id, "environment_id": env_id, "strategy": "canary",
              "candidate_version": "1.2.0", "provider_type": "k8s_rolling"},
    )
    assert rr.status_code == 201
    assert rr.json()["provider_mode"] in ("offline", "unavailable", "live")
    rid = rr.json()["id"]

    # idempotent create
    rr2 = await client.post(
        "/v1/delivery/release-reliability", headers=headers,
        json={"release_id": release_id, "environment_id": env_id, "strategy": "canary"},
    )
    assert rr2.status_code == 201
    assert rr2.json()["id"] == rid

    verify = await client.post(f"/v1/delivery/release-reliability/{rid}/verify", headers=headers)
    assert verify.status_code == 200
    assert "gate" in verify.json()

    rollout = await client.post(
        f"/v1/delivery/release-reliability/{rid}/propose-rollout", headers=headers,
        json={"strategy": "canary", "traffic_steps": [10, 50, 100]},
    )
    assert rollout.status_code == 200
    assert rollout.json()["simulated"] is True

    hist = await client.get(f"/v1/delivery/release-reliability/{rid}/history", headers=headers)
    assert hist.status_code == 200

    analytics = await client.get("/v1/delivery/release-analytics", headers=headers)
    assert analytics.status_code == 200


@pytest.mark.asyncio
async def test_tenant_isolation_release_reliability(client):
    _, tokens1 = await create_authenticated_user(client, email="rrt1@e.com", username="rrtuser1")
    _, tokens2 = await create_authenticated_user(client, email="rrt2@e.com", username="rrtuser2")
    h1 = auth_headers(tokens1["access_token"])
    h2 = auth_headers(tokens2["access_token"])
    envs = await client.get("/v1/delivery/environments", headers=h1)
    env_id = envs.json()[0]["id"]
    rel = await client.post(
        "/v1/delivery/releases", headers=h1, json={"version": "2.0.0", "environment_id": env_id},
    )
    rr = await client.post(
        "/v1/delivery/release-reliability", headers=h1,
        json={"release_id": rel.json()["id"], "environment_id": env_id},
    )
    other = await client.get(f"/v1/delivery/release-reliability/{rr.json()['id']}", headers=h2)
    assert other.status_code in (403, 404)


@pytest.mark.asyncio
async def test_promotion_policies_and_freeze(client):
    _, tokens = await create_authenticated_user(client, email="rrp1@e.com", username="rrpuser1")
    headers = auth_headers(tokens["access_token"])
    policies = await client.get("/v1/delivery/promotion-policies", headers=headers)
    assert policies.status_code == 200
    assert len(policies.json()) >= 4
    now = datetime.now(UTC)
    fw = await client.post(
        "/v1/delivery/freeze-windows", headers=headers,
        json={"name": "Holiday freeze", "environment_tier": "PRODUCTION",
              "starts_at": now.isoformat(), "ends_at": (now + timedelta(days=7)).isoformat()},
    )
    assert fw.status_code == 201
    queue = await client.get("/v1/delivery/promotion-queue", headers=headers)
    assert queue.status_code == 200


def test_migration_0032_revision_chain():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0032_release_reliability.py"
    spec = importlib.util.spec_from_file_location("migration_0032", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.down_revision == "0031_security_production"
    assert m.revision == "0032_release_reliability"
