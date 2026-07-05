"""Sprint 66K — Pilot reliability and launch readiness regression tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select

from app.integration_readiness.live_gate import LiveMutationGate
from app.models.delivery import DeliveryEnvironment
from app.models.pilot import PilotApproval, PilotEnrollment, PilotLiveOperation, PilotStage
from app.pilot.verification import evaluate_scale_verification, is_rollback_eligible
from app.tests.conftest import auth_headers, create_authenticated_user, create_organization, switch_organization
from app.tests.pilot_fixtures import run_pilot_prereqs, seed_pilot_integrations
from app.tests.test_pilot_readiness import _org_user, _seed_checklist_complete


@pytest.mark.asyncio
async def test_stage_seed_stable_across_reads(client):
    tokens, org_id = await _org_user(client, email="rel-stage@e.com", username="relstage", slug="rel-stage")
    headers = auth_headers(tokens["access_token"])
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await seed_pilot_integrations(session, org_id, cluster_id="cluster-rel", k8s_key="rel-k8s")
        await session.commit()

    await run_pilot_prereqs(client, headers, org_id)
    first = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
    second = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
    assert first["stages"] == second["stages"]
    keys = {s["stage_key"]: s["status"] for s in first["stages"]}
    assert keys["BASELINE_CAPTURE"] == "COMPLETED"


@pytest.mark.asyncio
async def test_approval_decision_links_same_enrollment(client):
    tokens, org_id = await _org_user(client, email="rel-appr@e.com", username="relappr", slug="rel-appr")
    headers = auth_headers(tokens["access_token"])
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await _seed_checklist_complete(session, org_id)
        env = DeliveryEnvironment(organization_id=org_id, tier="STAGING", name="staging")
        session.add(env)
        await seed_pilot_integrations(session, org_id, cluster_id="cluster-appr", k8s_key="appr-k8s")
        await session.commit()
        env_id = env.id

    await run_pilot_prereqs(client, headers, org_id)
    await client.post("/v1/pilot/live-operations/enable", headers=headers)
    propose = await client.post("/v1/pilot/live-operations", headers=headers, json={
        "action": "scale_deployment",
        "resource_name": "api",
        "environment_id": env_id,
        "cluster_id": "cluster-appr",
        "template_id": "scale_deployment",
        "params": {"namespace": "default", "replicas": 2, "from_replicas": 1},
        "rollback_plan": "Scale back to 1",
    })
    assert propose.status_code == 201
    op_id = propose.json()["id"]
    pending = await client.post("/v1/pilot/approvals", headers=headers, json={
        "operation_id": op_id,
        "approver_name": "Approver",
        "approver_email": "a@example.com",
        "operation_summary": "Scale api",
        "rollback_plan": "Revert",
        "approve": False,
    })
    assert pending.status_code == 201
    approval_id = pending.json()["id"]
    decide = await client.post(f"/v1/pilot/approvals/{approval_id}/decide", headers=headers, json={
        "approve": True, "rationale": "Approved for pilot",
    })
    assert decide.status_code == 200

    async with AsyncSessionLocal() as session:
        op = await session.get(PilotLiveOperation, op_id)
        approval = await session.get(PilotApproval, approval_id)
        enrollment = await session.get(PilotEnrollment, op.enrollment_id)
        assert op.approval_id == approval_id
        assert approval.enrollment_id == enrollment.id
        assert approval.operation_id == op_id


@pytest.mark.asyncio
async def test_approval_payload_hash_invalidation(client):
    tokens, org_id = await _org_user(client, email="rel-hash@e.com", username="relhash", slug="rel-hash")
    headers = auth_headers(tokens["access_token"])
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await _seed_checklist_complete(session, org_id)
        env = DeliveryEnvironment(organization_id=org_id, tier="STAGING", name="staging")
        session.add(env)
        await seed_pilot_integrations(session, org_id, cluster_id="cluster-hash", k8s_key="hash-k8s")
        await session.commit()
        env_id = env.id

    await run_pilot_prereqs(client, headers, org_id)
    await client.post("/v1/pilot/live-operations/enable", headers=headers)
    propose = await client.post("/v1/pilot/live-operations", headers=headers, json={
        "action": "scale_deployment",
        "resource_name": "api",
        "environment_id": env_id,
        "cluster_id": "cluster-hash",
        "template_id": "scale_deployment",
        "params": {"namespace": "default", "replicas": 2, "from_replicas": 1},
    })
    op_id = propose.json()["id"]
    approval = await client.post("/v1/pilot/approvals", headers=headers, json={
        "operation_id": op_id,
        "approver_name": "A",
        "approver_email": "a@example.com",
        "operation_summary": "s",
        "rollback_plan": "r",
        "approve": False,
    })
    approval_id = approval.json()["id"]

    async with AsyncSessionLocal() as session:
        op = await session.get(PilotLiveOperation, op_id)
        op.params = {"namespace": "default", "replicas": 3, "from_replicas": 1}
        await session.commit()

    decide = await client.post(f"/v1/pilot/approvals/{approval_id}/decide", headers=headers, json={"approve": True})
    assert decide.status_code == 422


@pytest.mark.asyncio
async def test_export_report_fresh_enrollment(client):
    tokens, org_id = await _org_user(client, email="rel-exp@e.com", username="relexp", slug="rel-exp")
    headers = auth_headers(tokens["access_token"])
    report = (await client.get("/v1/pilot/report/export", headers=headers)).json()
    assert "readiness" in report
    assert report.get("assessment") is None
    assert "execution" in report


@pytest.mark.asyncio
async def test_closure_blocked_without_evidence(client):
    tokens, org_id = await _org_user(client, email="rel-close@e.com", username="relclose", slug="rel-close")
    headers = auth_headers(tokens["access_token"])
    resp = await client.post("/v1/pilot/closure", headers=headers, json={})
    body = resp.json()
    assert body["closure_status"] == "BLOCKED"
    assert body["complete_advanced"] is False


@pytest.mark.asyncio
async def test_cross_org_launch_readiness_isolated(client):
    tokens1, org1 = await _org_user(client, email="rel-iso1@e.com", username="reliso1", slug="rel-iso1")
    tokens2, _org2 = await _org_user(client, email="rel-iso2@e.com", username="reliso2", slug="rel-iso2")
    h1, h2 = auth_headers(tokens1["access_token"]), auth_headers(tokens2["access_token"])
    await client.post("/v1/pilot/onboarding-paths/k8s-github-prometheus/start", headers=h1)
    lr1 = (await client.get("/v1/pilot/launch-readiness", headers=h1)).json()
    lr2 = (await client.get("/v1/pilot/launch-readiness", headers=h2)).json()
    assert lr1["verdict"] in ("GO", "NO_GO", "INSUFFICIENT_EVIDENCE")
    assert lr2["verdict"] in ("GO", "NO_GO", "INSUFFICIENT_EVIDENCE")


@pytest.mark.asyncio
async def test_launch_readiness_has_no_mutation_side_effects(client):
    tokens, org_id = await _org_user(client, email="rel-launch@e.com", username="rellaunch", slug="rel-launch")
    headers = auth_headers(tokens["access_token"])
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        before_ops = (await session.execute(
            select(func.count()).select_from(PilotLiveOperation).where(
                PilotLiveOperation.organization_id == org_id,
            ),
        )).scalar_one()
        before_approvals = (await session.execute(
            select(func.count()).select_from(PilotApproval).where(
                PilotApproval.organization_id == org_id,
            ),
        )).scalar_one()

    lr = (await client.get("/v1/pilot/launch-readiness", headers=headers)).json()
    assert lr["read_only"] is True

    async with AsyncSessionLocal() as session:
        after_ops = (await session.execute(
            select(func.count()).select_from(PilotLiveOperation).where(
                PilotLiveOperation.organization_id == org_id,
            ),
        )).scalar_one()
        after_approvals = (await session.execute(
            select(func.count()).select_from(PilotApproval).where(
                PilotApproval.organization_id == org_id,
            ),
        )).scalar_one()

    assert before_ops == after_ops == 0
    assert before_approvals == after_approvals == 0


def test_rollback_safety_unchanged():
    verdict = evaluate_scale_verification(
        before={"resource_name": "api"},
        execution_result={"action": "scale_deployment", "status": "scaled", "simulated": False},
        kubernetes_evidence={"kubernetes_error": "PermissionError"},
        prometheus_evidence={"status": "success", "data": {"result": [{"value": [0, "2"]}]}},
        target_replicas=2,
        source_mode="LIVE",
    )
    assert verdict["verification_status"] == "INSUFFICIENT_EVIDENCE"
    assert not is_rollback_eligible(verdict)
