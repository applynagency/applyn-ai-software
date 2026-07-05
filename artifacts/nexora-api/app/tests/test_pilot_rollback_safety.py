"""Sprint 66J — Rollback safety regression tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.pilot.verification import (
    evaluate_scale_verification,
    is_rollback_eligible,
)
from app.services.pilot import PilotService
from app.tests.conftest import auth_headers
from app.tests.pilot_fixtures import run_pilot_prereqs, seed_pilot_integrations
from app.tests.test_pilot_readiness import _org_user

_BEFORE = {"resource_name": "pilot-demo", "captured": "pre_execution"}
_EXEC_OK = {"action": "scale_deployment", "status": "scaled", "replicas": 2, "simulated": False}
_TARGET = 2


def _k8s(*, desired: int, available: int, ready_pods: int = 2, rollout_failed: bool = False) -> dict:
    pods = [{"name": f"p{i}", "ready": True, "restarts": 0} for i in range(ready_pods)]
    return {
        "deployment": {
            "desired_replicas": desired,
            "available_replicas": available,
            "ready_replicas": available,
        },
        "pods": pods,
        "warning_events": [],
        "rollout_failed": rollout_failed,
        "total_restarts": 0,
    }


def _prom(replicas: int | None) -> dict:
    if replicas is None:
        return {"status": "success", "data": {"result": []}}
    return {
        "status": "success",
        "data": {"result": [{"value": [0, str(replicas)]}]},
    }


class TestRollbackSafetySemantics:
    def test_permission_error_insufficient_no_rollback(self):
        verdict = evaluate_scale_verification(
            before=_BEFORE,
            execution_result=_EXEC_OK,
            kubernetes_evidence={"kubernetes_error": "PermissionError"},
            prometheus_evidence=_prom(2),
            target_replicas=_TARGET,
            source_mode="LIVE",
        )
        assert verdict["verification_status"] == "INSUFFICIENT_EVIDENCE"
        assert not is_rollback_eligible(verdict)
        assert verdict["rollback_eligible"] is False

    def test_prometheus_unavailable_insufficient_no_rollback(self):
        verdict = evaluate_scale_verification(
            before=_BEFORE,
            execution_result=_EXEC_OK,
            kubernetes_evidence=_k8s(desired=2, available=2),
            prometheus_evidence={"status": "error", "prometheus_error": "connection_refused"},
            target_replicas=_TARGET,
            source_mode="LIVE",
        )
        assert verdict["verification_status"] == "INSUFFICIENT_EVIDENCE"
        assert not is_rollback_eligible(verdict)

    def test_missing_metric_series_insufficient_no_rollback(self):
        verdict = evaluate_scale_verification(
            before=_BEFORE,
            execution_result=_EXEC_OK,
            kubernetes_evidence=_k8s(desired=2, available=2),
            prometheus_evidence={"status": "success", "data": {"result": []}},
            target_replicas=_TARGET,
            source_mode="LIVE",
        )
        assert verdict["verification_status"] == "INSUFFICIENT_EVIDENCE"
        assert "prometheus_metric_series_missing" in (verdict.get("reasons") or [])
        assert not is_rollback_eligible(verdict)

    def test_replica_mismatch_verification_failed_rollback_eligible(self):
        verdict = evaluate_scale_verification(
            before=_BEFORE,
            execution_result=_EXEC_OK,
            kubernetes_evidence=_k8s(desired=2, available=1, ready_pods=1),
            prometheus_evidence=_prom(1),
            target_replicas=_TARGET,
            source_mode="LIVE",
        )
        assert verdict["verification_status"] == "VERIFICATION_FAILED"
        assert is_rollback_eligible(verdict)
        assert verdict["rollback_eligible"] is True
        assert verdict["failed_verification_rules"]

    def test_rollout_failed_verification_failed_rollback_eligible(self):
        verdict = evaluate_scale_verification(
            before=_BEFORE,
            execution_result=_EXEC_OK,
            kubernetes_evidence=_k8s(desired=2, available=2, rollout_failed=True),
            prometheus_evidence=_prom(2),
            target_replicas=_TARGET,
            source_mode="LIVE",
        )
        assert verdict["verification_status"] == "VERIFICATION_FAILED"
        assert is_rollback_eligible(verdict)
        assert "kubernetes_rollout_failed" in verdict["failed_verification_rules"]

    def test_verified_dual_signal_no_rollback(self):
        verdict = evaluate_scale_verification(
            before=_BEFORE,
            execution_result=_EXEC_OK,
            kubernetes_evidence=_k8s(desired=2, available=2),
            prometheus_evidence=_prom(2),
            target_replicas=_TARGET,
            source_mode="LIVE",
        )
        assert verdict["verification_status"] == "VERIFIED"
        assert not is_rollback_eligible(verdict)
        assert verdict["rollback_eligible"] is False


@pytest.mark.asyncio
async def test_verify_endpoint_never_rolls_back_on_insufficient_evidence(client):
    """Integration: INSUFFICIENT_EVIDENCE must not invoke rollback."""
    tokens, org_id = await _org_user(client, email="rb-safe@e.com", username="rbsafe", slug="rb-safe")
    headers = auth_headers(tokens["access_token"])
    from app.database.session import AsyncSessionLocal
    from app.models.delivery import DeliveryEnvironment
    from app.models.pilot import PilotLiveOperation
    from app.tests.test_pilot_readiness import _seed_checklist_complete

    async with AsyncSessionLocal() as session:
        await _seed_checklist_complete(session, org_id)
        env = DeliveryEnvironment(organization_id=org_id, tier="STAGING", name="staging")
        session.add(env)
        await seed_pilot_integrations(session, org_id, cluster_id="cluster-rb", k8s_key="rb-k8s")
        await session.commit()
        env_id = env.id

    await run_pilot_prereqs(client, headers, org_id)
    await client.post("/v1/pilot/live-operations/enable", headers=headers)

    propose = await client.post("/v1/pilot/live-operations", headers=headers, json={
        "action": "scale_deployment",
        "resource_name": "api",
        "environment_id": env_id,
        "cluster_id": "cluster-rb",
        "template_id": "scale_deployment",
        "params": {"namespace": "default", "replicas": 2, "from_replicas": 1},
        "rollback_plan": "Scale back to 1",
    })
    assert propose.status_code == 201
    op_id = propose.json()["id"]

    async with AsyncSessionLocal() as session:
        op = await session.get(PilotLiveOperation, op_id)
        op.status = "PENDING_VERIFICATION"
        op.source_mode = "LIVE"
        op.result = {"action": "scale_deployment", "status": "scaled", "replicas": 2}
        await session.commit()

    with patch.object(PilotService, "_attempt_pilot_rollback", new_callable=AsyncMock) as mock_rb:
        resp = await client.post(f"/v1/pilot/live-operations/{op_id}/verify", headers=headers, json={
            "kubernetes_evidence": {"kubernetes_error": "PermissionError"},
            "prometheus_evidence": {"status": "success", "data": {"result": [{"value": [0, "2"]}]}},
        })
        assert resp.status_code == 200
        assert resp.json()["verification_status"] == "INSUFFICIENT_EVIDENCE"
        mock_rb.assert_not_called()
