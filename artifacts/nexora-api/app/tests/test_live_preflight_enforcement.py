"""Sprint 65H — Live mutation preflight enforcement tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.integration_readiness.capabilities import build_capability_matrix, enforce_write_allowed
from app.integration_readiness.live_gate import (
    CONTROL_PLANE_CAPABILITIES,
    DELIVERY_CAPABILITIES,
    ENTERPRISE_MUTATION_CAPABILITIES,
    IAC_CAPABILITIES,
    LiveMutationGate,
    missing_capabilities,
    normalize_capabilities,
)
from app.integration_readiness.preflight import preflight_live_operation
from app.models.integration_readiness import IntConnectionRegistry
from app.release_reliability.health_gates import GATE_INSUFFICIENT, evaluate_health_gate


def test_normalize_capabilities_aliases():
    assert normalize_capabilities(["kubernetes.workloads.write"]) == ["write"]
    assert normalize_capabilities(["deployment.execute"]) == ["deploy"]


def test_missing_capabilities_detects_gaps():
    caps = build_capability_matrix("KUBERNETES", ["get", "list"])
    missing = missing_capabilities(caps, ["kubernetes.workloads.write"])
    assert "kubernetes.workloads.write" in missing


def test_read_only_k8s_blocks_writes():
    check = enforce_write_allowed(
        build_capability_matrix("KUBERNETES", ["get", "list"]),
        provider_mode="live", lifecycle_state="CONNECTED",
    )
    assert check["allowed"] is False


def test_simulation_never_auto_selected():
    result = preflight_live_operation(
        registry={"lifecycle_state": "FAILED", "provider_mode": "unavailable", "capabilities": {}},
        required_capabilities=["write"],
        environment_id=None, organization_id="org1", idempotency_key="k1",
        explicit_simulation=False,
    )
    assert result["allowed"] is False
    assert result["simulated"] is False


def test_explicit_simulation_labeled():
    result = preflight_live_operation(
        registry={"lifecycle_state": "DRAFT", "provider_mode": "unavailable", "capabilities": {}},
        required_capabilities=["write"],
        environment_id=None, organization_id="org1", idempotency_key="k1",
        explicit_simulation=True,
    )
    assert result["allowed"] is True
    assert result["simulated"] is True


def test_production_promotion_blocked_without_observability():
    signals = {"pod_ready": True, "rollout_status": "Complete", "_source_modes": {"metrics": "offline", "logs": "offline"}}
    gate = evaluate_health_gate(signals, is_production=True, environment_tier="PRODUCTION")
    assert gate["decision"] == GATE_INSUFFICIENT


def test_control_plane_capability_map_covers_scale():
    assert "scale_deployment" in CONTROL_PLANE_CAPABILITIES


def test_delivery_gitops_requires_sync():
    assert "gitops.sync" in DELIVERY_CAPABILITIES["GITOPS_SYNC"]


def test_iac_destroy_requires_destroy_cap():
    assert "iac.destroy" in IAC_CAPABILITIES["DESTROY"]


def test_enterprise_mutation_capability_map():
    assert "acknowledge_incident" in ENTERPRISE_MUTATION_CAPABILITIES
    assert "enterprise.incidents.write" in ENTERPRISE_MUTATION_CAPABILITIES["acknowledge_incident"]


def test_enterprise_providers_grant_write_capability():
    caps = build_capability_matrix("PAGERDUTY", ["read"])
    assert caps["write"] is True


@pytest.mark.asyncio
async def test_live_gate_blocks_offline_connection(setup_db):
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        row = IntConnectionRegistry(
            organization_id="org-h1",
            resource_type="kubernetes",
            resource_id="cluster-1",
            provider_type="KUBERNETES",
            lifecycle_state="CONNECTED",
            provider_mode="offline",
            capabilities={"write": True},
            credential_id="cred-1",
            last_validated_at=datetime.now(UTC),
            idempotency_key="gate-key-1",
        )
        session.add(row)
        await session.commit()
        gate = LiveMutationGate(session)
        result = await gate.preflight_mutation(
            organization_id="org-h1",
            actor_id="user-1",
            integration_connection_id=row.id,
            operation_type="control_plane.scale_deployment",
            resource_type="cp_operation",
            resource_id="op-1",
            idempotency_key="idem-1",
            required_capabilities=["kubernetes.workloads.write"],
            approval_satisfied=True,
            explicit_simulation=False,
        )
    assert result["allowed"] is False
    assert result["reason_code"] == "PROVIDER_NOT_LIVE"


@pytest.mark.asyncio
async def test_live_gate_allows_explicit_simulation(setup_db):
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        gate = LiveMutationGate(session)
        result = await gate.preflight_mutation(
            organization_id="org-h2",
            actor_id="user-1",
            integration_connection_id=None,
            operation_type="control_plane.scale_deployment",
            resource_type="cp_operation",
            resource_id="op-2",
            idempotency_key="idem-2",
            required_capabilities=["kubernetes.workloads.write"],
            explicit_simulation=True,
        )
    assert result["allowed"] is True
    assert result["simulated"] is True


@pytest.mark.asyncio
async def test_live_gate_blocks_stale_validation(setup_db):
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        row = IntConnectionRegistry(
            organization_id="org-h3",
            resource_type="kubernetes",
            resource_id="cluster-3",
            provider_type="KUBERNETES",
            lifecycle_state="CONNECTED",
            provider_mode="live",
            capabilities={"write": True},
            credential_id="cred-3",
            last_validated_at=datetime.now(UTC) - timedelta(hours=48),
            idempotency_key="gate-key-3",
        )
        session.add(row)
        await session.commit()
        gate = LiveMutationGate(session)
        result = await gate.preflight_mutation(
            organization_id="org-h3",
            actor_id="user-1",
            integration_connection_id=row.id,
            operation_type="iac.destroy",
            resource_type="pe_iac_run",
            resource_id="run-1",
            idempotency_key="idem-3",
            required_capabilities=["iac.destroy"],
            destroy=True,
        )
    assert result["allowed"] is False
    assert result["reason_code"] == "VALIDATION_STALE"


@pytest.mark.asyncio
async def test_control_plane_execute_blocks_without_live_preflight(client):
    from app.tests.conftest import auth_headers, create_authenticated_user, create_organization, switch_organization

    user, tokens = await create_authenticated_user(client, email="cp-h@e.com", username="cp_h_user")
    org = await create_organization(client, tokens["access_token"], name="CP H Org", slug="cp-h-org")
    tokens = await switch_organization(client, tokens["access_token"], org["id"])
    headers = auth_headers(tokens["access_token"])

    from app.database.session import AsyncSessionLocal
    from app.models.control_plane import ControlPlaneOperation, KubernetesCluster

    async with AsyncSessionLocal() as session:
        cluster = KubernetesCluster(
            organization_id=org["id"], name="test-cluster", credential_id="cred-x",
            distribution="VANILLA", health="UNKNOWN", created_by=user["id"],
        )
        session.add(cluster)
        await session.flush()
        op = ControlPlaneOperation(
            organization_id=org["id"],
            kind="SCALE_DEPLOYMENT",
            status="APPROVED",
            cluster_id=cluster.id,
            namespace="default",
            resource_name="api",
            params={"replicas": 3},
            requested_by=user["id"],
        )
        session.add(op)
        await session.flush()
        reg = IntConnectionRegistry(
            organization_id=org["id"],
            resource_type="kubernetes",
            resource_id=cluster.id,
            provider_type="KUBERNETES",
            lifecycle_state="CONNECTED",
            provider_mode="offline",
            capabilities={"write": True},
            credential_id="cred-x",
            last_validated_at=datetime.now(UTC),
            idempotency_key="cp-reg-1",
        )
        session.add(reg)
        await session.commit()
        op_id = op.id

    resp = await client.post(f"/v1/control-plane/operations/{op_id}/execute", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "FAILED"
    assert body.get("result", {}).get("blocked") is True


@pytest.mark.asyncio
async def test_delivery_execute_marks_simulated_when_explicit(client):
    from app.tests.conftest import auth_headers, create_authenticated_user, create_organization, switch_organization

    _, tokens = await create_authenticated_user(client, email="dlv-h@e.com", username="dlv_h_user")
    org = await create_organization(client, tokens["access_token"], name="DLV H Org", slug="dlv-h-org")
    tokens = await switch_organization(client, tokens["access_token"], org["id"])
    headers = auth_headers(tokens["access_token"])

    envs = await client.get("/v1/delivery/environments", headers=headers)
    env_id = envs.json()[0]["id"]
    rel = await client.post(
        "/v1/delivery/releases", headers=headers,
        json={"version": "2.0.0", "environment_id": env_id},
    )
    release_id = rel.json()["id"]
    prop = await client.post(
        "/v1/delivery/operations", headers=headers,
        json={"kind": "PROMOTE", "release_id": release_id, "environment_id": env_id,
              "params": {"explicit_simulation": True}},
    )
    op_id = prop.json()["id"]
    await client.post(f"/v1/delivery/operations/{op_id}/decide", headers=headers, json={"approved": True})
    resp = await client.post(f"/v1/delivery/operations/{op_id}/execute", headers=headers)
    assert resp.status_code == 200
    result = resp.json().get("result") or {}
    assert result.get("simulated") is True
