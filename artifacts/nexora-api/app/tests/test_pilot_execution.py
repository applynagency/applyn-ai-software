"""Sprint 66B — Real pilot execution readiness tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.integration_readiness.evidence import redact_text
from app.integration_readiness.live_gate import LiveMutationGate
from app.models.delivery import DeliveryEnvironment
from app.models.integration_readiness import IntConnectionRegistry
from app.models.pilot import PilotApproval, PilotEnrollment, PilotLiveOperation
from app.pilot.operations import PILOT_CATALOG_ACTIONS, PILOT_OPERATION_CATALOG
from app.pilot.stages import PILOT_STAGE_KEYS
from app.pilot.verification import evaluate_verification
from app.repositories.pilot import PilotEnrollmentRepo
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    switch_organization,
)
from app.tests.test_pilot_readiness import _org_user, _seed_checklist_complete
from app.tests.pilot_fixtures import run_pilot_prereqs, seed_pilot_integrations


async def _seed_pending_live_operation(client, headers, org_id, *, slug: str):
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await _seed_checklist_complete(session, org_id)
        env = DeliveryEnvironment(organization_id=org_id, tier="STAGING", name=f"staging-{slug}")
        session.add(env)
        await seed_pilot_integrations(session, org_id, cluster_id=f"cluster-{slug}", k8s_key=f"{slug}-k8s")
        await session.commit()
        env_id = env.id

    await run_pilot_prereqs(client, headers, org_id)
    await client.post("/v1/pilot/live-operations/enable", headers=headers)
    propose = await client.post("/v1/pilot/live-operations", headers=headers, json={
        "action": "restart_deployment",
        "resource_name": "api",
        "environment_id": env_id,
        "cluster_id": f"cluster-{slug}",
        "template_id": "restart_deployment",
    })
    assert propose.status_code == 201
    op_id = propose.json()["id"]
    approval = await client.post("/v1/pilot/approvals", headers=headers, json={
        "operation_id": op_id,
        "approver_name": "Pending Approver",
        "approver_email": "pending@example.com",
        "operation_summary": "Pending only",
        "rollback_plan": "Revert",
        "approve": False,
    })
    assert approval.status_code == 201
    return op_id, approval.json()["id"]


@pytest.mark.asyncio
async def test_execution_stages_seeded(client):
    tokens, _org_id = await _org_user(client, email="pexec-stage@e.com", username="pexecstage", slug="pexec-stage")
    headers = auth_headers(tokens["access_token"])
    await client.post("/v1/pilot/onboarding-paths/k8s-github-prometheus/start", headers=headers)
    status = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
    assert status["execution_status"] in ("IN_PROGRESS", "NOT_STARTED", "COMPLETED")
    keys = [s["stage_key"] for s in status["stages"]]
    assert keys == list(PILOT_STAGE_KEYS)


@pytest.mark.asyncio
async def test_stage_skip_prevention(client):
    tokens, _org_id = await _org_user(client, email="pexec-skip@e.com", username="pexecskip", slug="pexec-skip")
    headers = auth_headers(tokens["access_token"])
    resp = await client.post("/v1/pilot/execution/stages/VALIDATE/advance", headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_operation_catalog_allowlist(client):
    tokens, _org_id = await _org_user(client, email="pexec-cat@e.com", username="pexeccat", slug="pexec-cat")
    headers = auth_headers(tokens["access_token"])
    catalog = (await client.get("/v1/pilot/operations/catalog", headers=headers)).json()
    actions = {t["action"] for t in catalog}
    assert actions == set(PILOT_CATALOG_ACTIONS)
    assert "trigger_deployment" not in actions
    assert len(catalog) == len(PILOT_OPERATION_CATALOG)


@pytest.mark.asyncio
async def test_production_rejection(client):
    tokens, org_id = await _org_user(client, email="pexec-prod@e.com", username="pexecprod", slug="pexec-prod")
    headers = auth_headers(tokens["access_token"])
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await _seed_checklist_complete(session, org_id)
        env = DeliveryEnvironment(organization_id=org_id, tier="PRODUCTION", name="prod")
        session.add(env)
        await session.commit()
        env_id = env.id

    await client.post("/v1/pilot/live-operations/enable", headers=headers)
    resp = await client.post("/v1/pilot/live-operations", headers=headers, json={
        "action": "restart_deployment",
        "resource_name": "api",
        "environment_id": env_id,
        "template_id": "restart_deployment",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_approval_required_and_simulated_flow(client):
    tokens, org_id = await _org_user(client, email="pexec-appr@e.com", username="pexecappr", slug="pexec-appr")
    headers = auth_headers(tokens["access_token"])
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await _seed_checklist_complete(session, org_id)
        env = DeliveryEnvironment(organization_id=org_id, tier="STAGING", name="staging")
        session.add(env)
        await seed_pilot_integrations(session, org_id, cluster_id="cluster-exec", k8s_key="pexec-k8s")
        await session.commit()
        env_id = env.id

    await run_pilot_prereqs(client, headers, org_id)
    await client.post("/v1/pilot/live-operations/enable", headers=headers)
    propose = await client.post("/v1/pilot/live-operations", headers=headers, json={
        "action": "restart_deployment",
        "resource_name": "payments-api",
        "environment_id": env_id,
        "cluster_id": "cluster-exec",
        "template_id": "restart_deployment",
        "rollback_plan": "Revert rollout if probes fail",
    })
    assert propose.status_code == 201
    op = propose.json()
    token = op["confirmation_token"]

    no_approval = await client.post(f"/v1/pilot/live-operations/{op['id']}/confirm", headers=headers, json={
        "confirmation_token": token,
        "typed_confirmation": "payments-api",
        "approved": True,
    })
    assert no_approval.status_code == 422

    approval = await client.post("/v1/pilot/approvals", headers=headers, json={
        "operation_id": op["id"],
        "approver_name": "Customer Lead",
        "approver_email": "customer@example.com",
        "operation_summary": "Restart payments-api in staging",
        "rollback_plan": "Revert deployment if health checks fail",
        "approve": True,
    })
    assert approval.status_code == 201

    async def _sim_preflight(self, **kwargs):
        return {
            "allowed": True, "simulated": True, "correlation_id": "corr-exec-1",
            "connection_id": "conn-1", "evidence_context": {"mode": "simulated"},
        }

    with patch.object(LiveMutationGate, "preflight_mutation", new=_sim_preflight):
        ok = await client.post(f"/v1/pilot/live-operations/{op['id']}/confirm", headers=headers, json={
            "confirmation_token": token,
            "typed_confirmation": "payments-api",
            "approved": True,
        })
    assert ok.status_code == 200
    body = ok.json()
    assert body["status"] == "SUCCEEDED"
    assert body["verification_status"] == "VERIFIED"
    assert body["source_mode"] == "SIMULATED"


@pytest.mark.asyncio
async def test_pending_approval_does_not_complete_customer_stage(client):
    tokens, org_id = await _org_user(client, email="pexec-pend@e.com", username="pexecpend", slug="pexec-pend")
    headers = auth_headers(tokens["access_token"])
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await _seed_checklist_complete(session, org_id)
        env = DeliveryEnvironment(organization_id=org_id, tier="STAGING", name="staging")
        session.add(env)
        await seed_pilot_integrations(session, org_id, cluster_id="cluster-pend", k8s_key="pend-k8s")
        await session.commit()
        env_id = env.id

    await run_pilot_prereqs(client, headers, org_id)
    await client.post("/v1/pilot/live-operations/enable", headers=headers)
    propose = await client.post("/v1/pilot/live-operations", headers=headers, json={
        "action": "restart_deployment",
        "resource_name": "api",
        "environment_id": env_id,
        "cluster_id": "cluster-pend",
        "template_id": "restart_deployment",
    })
    assert propose.status_code == 201
    op_id = propose.json()["id"]

    approval = await client.post("/v1/pilot/approvals", headers=headers, json={
        "operation_id": op_id,
        "approver_name": "Pending Approver",
        "approver_email": "pending@example.com",
        "operation_summary": "Pending only",
        "rollback_plan": "Revert",
        "approve": False,
    })
    assert approval.status_code == 201
    body = approval.json()
    assert body["status"] == "PENDING"
    assert body["approved_at"] is None

    status = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
    stages = {s["stage_key"]: s["status"] for s in status["stages"]}
    assert stages["PROPOSE_OPERATION"] == "COMPLETED"
    assert stages["CUSTOMER_APPROVAL"] == "PENDING"


@pytest.mark.asyncio
async def test_decide_pending_approval_and_execution_readiness(client):
    tokens, org_id = await _org_user(client, email="pexec-dec@e.com", username="pexecdec", slug="pexec-dec")
    headers = auth_headers(tokens["access_token"])
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await _seed_checklist_complete(session, org_id)
        env = DeliveryEnvironment(organization_id=org_id, tier="STAGING", name="staging")
        session.add(env)
        await seed_pilot_integrations(session, org_id, cluster_id="cluster-dec", k8s_key="dec-k8s")
        await session.commit()
        env_id = env.id

    await run_pilot_prereqs(client, headers, org_id)
    await client.post("/v1/pilot/live-operations/enable", headers=headers)
    propose = await client.post("/v1/pilot/live-operations", headers=headers, json={
        "action": "restart_deployment",
        "resource_name": "api",
        "environment_id": env_id,
        "cluster_id": "cluster-dec",
        "template_id": "restart_deployment",
        "rollback_plan": "Revert rollout",
    })
    assert propose.status_code == 201
    op_id = propose.json()["id"]

    approval = await client.post("/v1/pilot/approvals", headers=headers, json={
        "operation_id": op_id,
        "approver_name": "Pending Approver",
        "approver_email": "pending@example.com",
        "operation_summary": "Pending only",
        "rollback_plan": "Revert",
        "approve": False,
    })
    assert approval.status_code == 201
    approval_id = approval.json()["id"]

    decide = await client.post(
        f"/v1/pilot/approvals/{approval_id}/decide",
        headers=headers,
        json={"approve": True, "rationale": "Test internal approval rationale"},
    )
    assert decide.status_code == 200
    body = decide.json()
    assert body["status"] == "APPROVED"
    assert body["approved_at"] is not None
    assert body["decision_rationale"] == "Test internal approval rationale"

    status = (await client.get("/v1/pilot/execution/status", headers=headers)).json()
    stages = {s["stage_key"]: s["status"] for s in status["stages"]}
    assert stages["CUSTOMER_APPROVAL"] == "COMPLETED"
    assert stages["EXECUTE"] == "PENDING"

    op = (await client.get(f"/v1/pilot/live-operations/{op_id}", headers=headers)).json()
    assert op["status"] == "PENDING_CONFIRMATION"

    async def _live_preflight(self, **kwargs):
        return {
            "allowed": True,
            "simulated": False,
            "correlation_id": "corr-readiness-1",
            "connection_id": "conn-1",
            "evidence_context": {"mode": "live"},
        }

    with patch.object(LiveMutationGate, "preflight_mutation", new=_live_preflight):
        readiness = await client.post(
            f"/v1/pilot/live-operations/{op_id}/execution-readiness",
            headers=headers,
        )
    assert readiness.status_code == 200
    readiness_body = readiness.json()
    assert readiness_body["ready_for_typed_confirmation"] is True
    assert readiness_body["kubernetes_mutation_called"] is False
    assert readiness_body["provider_mutation_called"] is False
    assert readiness_body["remaining_required_action"] == "typed confirmation"


def test_approval_payload_hash_changes_on_params():
    from app.services.pilot_execution import _payload_hash
    h1 = _payload_hash("scale_deployment", "api", "env-1", {})
    h2 = _payload_hash("scale_deployment", "api", "env-1", {"replicas": 3})
    assert h1 != h2


@pytest.mark.asyncio
async def test_kill_switch_and_cooldown(client, monkeypatch):
    tokens, org_id = await _org_user(client, email="pexec-safe@e.com", username="pexecsafe", slug="pexec-safe")
    headers = auth_headers(tokens["access_token"])
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        enrollment = await _seed_checklist_complete(session, org_id)
        enrollment.live_operations_enabled = True
        enrollment.kill_switch = True
        await session.commit()

    ks = await client.post("/v1/pilot/safety/kill-switch", headers=headers, json={"enabled": True})
    assert ks.status_code == 200
    assert ks.json()["kill_switch"] is True

    async with AsyncSessionLocal() as session:
        env = DeliveryEnvironment(organization_id=org_id, tier="STAGING", name="staging")
        session.add(env)
        await session.commit()
        env_id = env.id
        enrollment = await PilotEnrollmentRepo(session).get_for_org(org_id)
        enrollment.kill_switch = False
        enrollment.operation_count = enrollment.operation_limit
        await session.commit()

    resp = await client.post("/v1/pilot/live-operations", headers=headers, json={
        "action": "restart_deployment",
        "resource_name": "api",
        "environment_id": env_id,
    })
    assert resp.status_code == 422


def test_verification_never_success_without_evidence():
    verdict = evaluate_verification(
        before={"status": "Ready"},
        after={},
        execution_result={"simulated": False},
        source_mode="UNAVAILABLE",
    )
    assert verdict["verification_status"] == "INSUFFICIENT_EVIDENCE"


def test_scale_verification_requires_k8s_and_prometheus():
    from app.pilot.verification import evaluate_scale_verification

    k8s = {
        "deployment": {"desired_replicas": 2, "available_replicas": 2, "ready_replicas": 2},
        "pods": [{"name": "a", "ready": True, "restarts": 0}, {"name": "b", "ready": True, "restarts": 0}],
        "warning_events": [],
        "rollout_failed": False,
        "total_restarts": 0,
    }
    prom = {"data": {"result": [{"value": [0, "2"]}]}}
    verdict = evaluate_scale_verification(
        before={"kubernetes": {"total_restarts": 0}},
        execution_result={"status": "scaled", "replicas": 2},
        kubernetes_evidence=k8s,
        prometheus_evidence=prom,
        target_replicas=2,
        source_mode="LIVE",
    )
    assert verdict["verification_status"] == "VERIFIED"

    missing_prom = evaluate_scale_verification(
        before={},
        execution_result={"status": "scaled"},
        kubernetes_evidence=k8s,
        prometheus_evidence=None,
        target_replicas=2,
        source_mode="LIVE",
    )
    assert missing_prom["verification_status"] == "INSUFFICIENT_EVIDENCE"


def test_evidence_pack_redaction():
    from app.pilot.evidence_pack import build_evidence_pack
    pack = build_evidence_pack({"token": "Bearer secret123", "nested": {"kubeconfig": "api-key=abc"}})
    blob = json.dumps(pack)
    assert "secret123" not in blob
    assert pack["redacted"] is True


@pytest.mark.asyncio
async def test_evidence_pack_export(client):
    tokens, _org_id = await _org_user(client, email="pexec-pack@e.com", username="pexecpack", slug="pexec-pack")
    headers = auth_headers(tokens["access_token"])
    await client.post("/v1/pilot/onboarding-paths/k8s-github-prometheus/start", headers=headers)
    pack = (await client.get("/v1/pilot/evidence-pack/export", headers=headers)).json()
    assert "json_pack" in pack
    assert pack["json_pack"]["redacted"] is True
    assert pack["markdown"]
    assert pack["html"]


@pytest.mark.asyncio
async def test_tenant_isolation_approvals(client):
    tokens1, org1 = await _org_user(client, email="pexec-iso1@e.com", username="pexeciso1", slug="pexec-iso1")
    tokens2, org2 = await _org_user(client, email="pexec-iso2@e.com", username="pexeciso2", slug="pexec-iso2")
    h1, h2 = auth_headers(tokens1["access_token"]), auth_headers(tokens2["access_token"])
    status1 = (await client.get("/v1/pilot/execution/status", headers=h1)).json()
    status2 = (await client.get("/v1/pilot/execution/status", headers=h2)).json()
    assert status1["enrollment_id"] != status2["enrollment_id"]


def test_migration_0035_chain():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0035_pilot_execution.py"
    spec = importlib.util.spec_from_file_location("m0035", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.revision == "0035_pilot_execution"
    assert m.down_revision == "0034_pilot_readiness"


def test_operator_execution_console_label_mapping():
    from app.pilot.customer_portal import operator_execution_console_label

    assert operator_execution_console_label("AWAITING_APPROVAL", "PENDING") == "Waiting for customer approval"
    assert operator_execution_console_label("PENDING_CONFIRMATION", "REJECTED") == "Blocked"
    assert operator_execution_console_label("PENDING_CONFIRMATION", "APPROVED", ready_for_typed_confirmation=True) == (
        "Ready for typed confirmation"
    )


@pytest.mark.asyncio
async def test_list_live_operations_includes_awaiting_approval(client):
    tokens, org_id = await _org_user(client, email="pexec-list@e.com", username="pexeclist", slug="pexec-list")
    headers = auth_headers(tokens["access_token"])
    op_id, _approval_id = await _seed_pending_live_operation(client, headers, org_id, slug="list")

    listed = await client.get("/v1/pilot/live-operations", headers=headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    ids = {item["id"] for item in body["items"]}
    assert op_id in ids
    match = next(item for item in body["items"] if item["id"] == op_id)
    assert match["status"] == "AWAITING_APPROVAL"
    assert match["approval_status"] == "PENDING"
    assert match["operator_label"] == "Waiting for customer approval"


@pytest.mark.asyncio
async def test_list_live_operations_filtered_by_active_organization(client):
    tokens, org_a = await _org_user(client, email="pexec-orga@e.com", username="pexecorga", slug="pexec-orga")
    headers_a = auth_headers(tokens["access_token"])
    op_id, _ = await _seed_pending_live_operation(client, headers_a, org_a, slug="orga")

    org_b = await create_organization(client, tokens["access_token"], name="Other Org", slug="pexec-orgb")
    tokens_b = await switch_organization(client, tokens["access_token"], org_b["id"])
    headers_b = auth_headers(tokens_b["access_token"])

    listed_b = await client.get("/v1/pilot/live-operations", headers=headers_b)
    assert listed_b.status_code == 200
    assert op_id not in {item["id"] for item in listed_b.json()["items"]}

    tokens_a = await switch_organization(client, tokens_b["access_token"], org_a)
    listed_a = await client.get("/v1/pilot/live-operations", headers=auth_headers(tokens_a["access_token"]))
    assert op_id in {item["id"] for item in listed_a.json()["items"]}


@pytest.mark.asyncio
async def test_list_detail_readiness_do_not_mutate_operation(client):
    tokens, org_id = await _org_user(client, email="pexec-ro@e.com", username="pexecro", slug="pexec-ro")
    headers = auth_headers(tokens["access_token"])
    op_id, _ = await _seed_pending_live_operation(client, headers, org_id, slug="ro")

    before = (await client.get(f"/v1/pilot/live-operations/{op_id}", headers=headers)).json()
    assert before["status"] == "AWAITING_APPROVAL"

    await client.get("/v1/pilot/live-operations", headers=headers)
    await client.get(f"/v1/pilot/live-operations/{op_id}", headers=headers)
    await client.get(f"/v1/pilot/live-operations/{op_id}/operator-handoff", headers=headers)
    readiness = await client.post(
        f"/v1/pilot/live-operations/{op_id}/execution-readiness",
        headers=headers,
    )
    assert readiness.status_code == 200

    after = (await client.get(f"/v1/pilot/live-operations/{op_id}", headers=headers)).json()
    assert after["status"] == before["status"] == "AWAITING_APPROVAL"
    assert after["verification_status"] == before.get("verification_status")
