"""Sprint 67B — Customer pilot portal tests."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select

from app.models.pilot import PilotApproval, PilotEnrollment, PilotLiveOperation, PilotStage
from app.tests.conftest import auth_headers, create_authenticated_user, create_organization, switch_organization
from app.tests.pilot_fixtures import run_pilot_prereqs, seed_pilot_integrations
from app.tests.test_pilot_readiness import _seed_checklist_complete

API = "/v1/customer-pilot"
PILOT = "/v1/pilot"


async def _headers_org(client, *, email: str, username: str, slug: str):
    _, tokens = await create_authenticated_user(client, email=email, username=username)
    org = await create_organization(client, tokens["access_token"], name=slug, slug=slug)
    tokens = await switch_organization(client, tokens["access_token"], org["id"])
    return auth_headers(tokens["access_token"]), org["id"]


async def _setup_pilot_op(client, headers, org_id):
    from app.database.session import AsyncSessionLocal
    from app.models.delivery import DeliveryEnvironment

    async with AsyncSessionLocal() as session:
        await _seed_checklist_complete(session, org_id)
        env = DeliveryEnvironment(organization_id=org_id, tier="STAGING", name="staging")
        session.add(env)
        await seed_pilot_integrations(session, org_id, cluster_id="cluster-cp", k8s_key="cp-k8s")
        await session.commit()
        env_id = env.id

    await run_pilot_prereqs(client, headers, org_id)
    await client.post(f"{PILOT}/live-operations/enable", headers=headers)
    propose = await client.post(f"{PILOT}/live-operations", headers=headers, json={
        "action": "scale_deployment",
        "resource_name": "api",
        "environment_id": env_id,
        "cluster_id": "cluster-cp",
        "template_id": "scale_deployment",
        "params": {"namespace": "default", "replicas": 2, "from_replicas": 1},
        "rollback_plan": "Scale back to 1",
    })
    assert propose.status_code == 201, propose.text
    op_id = propose.json()["id"]
    pending = await client.post(f"{PILOT}/approvals", headers=headers, json={
        "operation_id": op_id,
        "approver_name": "Customer Approver",
        "approver_email": "approver@customer.example",
        "operation_summary": "Scale api for pilot",
        "rollback_plan": "Scale back to 1",
        "approve": False,
    })
    assert pending.status_code == 201
    return op_id, pending.json()["id"], propose.json()["payload_hash"]


@pytest.mark.asyncio
async def test_customer_portal_overview(client):
    headers, org_id = await _headers_org(client, email="cp-overview@e.com", username="cpov", slug="cp-overview")
    resp = await client.get(f"{API}/overview", headers=headers)
    assert resp.status_code == 200
    assert "portal_visible" in resp.json()


@pytest.mark.asyncio
async def test_tenant_isolation_customer_pilot(client):
    h1, org1 = await _headers_org(client, email="cp-iso1@e.com", username="cpiso1", slug="cp-iso1")
    user2, tokens2 = await create_authenticated_user(
        client, email="cp-iso2@e.com", username="cpiso2", password="Pass123!",
    )
    org2 = await create_organization(client, tokens2["access_token"], name="Iso2", slug="cp-iso2")
    switched = await switch_organization(client, tokens2["access_token"], org2["id"])
    h2 = auth_headers(switched["access_token"])

    op_id, _, _ = await _setup_pilot_op(client, h1, org1)
    denied = await client.get(f"{API}/operation/{op_id}", headers=h2)
    assert denied.status_code == 404


@pytest.mark.asyncio
async def test_production_rejection_on_operation_view(client):
    headers, org_id = await _headers_org(client, email="cp-prod@e.com", username="cpprod", slug="cp-prod")
    from app.database.session import AsyncSessionLocal
    from app.models.delivery import DeliveryEnvironment
    from app.models.pilot import PilotLiveOperation, PilotEnrollment

    async with AsyncSessionLocal() as session:
        env = DeliveryEnvironment(organization_id=org_id, tier="PRODUCTION", name="prod")
        session.add(env)
        enrollment = PilotEnrollment(organization_id=org_id, status="ACTIVE")
        session.add(enrollment)
        await session.flush()
        op = PilotLiveOperation(
            organization_id=org_id,
            enrollment_id=enrollment.id,
            action="scale_deployment",
            resource_name="api",
            environment_id=env.id,
            status="AWAITING_APPROVAL",
            created_by="x",
        )
        session.add(op)
        await session.commit()
        op_id = op.id

    resp = await client.get(f"{API}/operation/{op_id}", headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_customer_cannot_confirm_execute(client):
    headers, org_id = await _headers_org(client, email="cp-noconf@e.com", username="cpnc", slug="cp-noconf")
    op_id, approval_id, phash = await _setup_pilot_op(client, headers, org_id)

    decide = await client.post(f"{API}/operation/{op_id}/approval/decide", headers=headers, json={
        "approver_name": "Customer Approver",
        "approver_email": "approver@customer.example",
        "approve": True,
        "rationale": "Approved for controlled pilot test",
        "payload_hash_acknowledged": phash,
        "rollback_plan_acknowledged": True,
    })
    assert decide.status_code == 200

    confirm = await client.post(f"{PILOT}/live-operations/{op_id}/confirm", headers=headers, json={
        "confirmation_token": "invalid",
        "typed_confirmation": "api",
        "approved": True,
    })
    assert confirm.status_code in (400, 422)


@pytest.mark.asyncio
async def test_approval_package_immutability(client):
    headers, org_id = await _headers_org(client, email="cp-pkg@e.com", username="cppkg", slug="cp-pkg")
    op_id, approval_id, phash = await _setup_pilot_op(client, headers, org_id)

    pkg1 = await client.get(f"{API}/operation/{op_id}/approval-package", headers=headers)
    assert pkg1.status_code == 200
    assert pkg1.json()["immutable"] is True
    hash1 = pkg1.json()["payload_hash"]

    from app.database.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        op = await session.get(PilotLiveOperation, op_id)
        op.params = {"namespace": "default", "replicas": 3, "from_replicas": 1}
        await session.commit()

    decide = await client.post(f"{API}/operation/{op_id}/approval/decide", headers=headers, json={
        "approver_name": "Customer Approver",
        "approver_email": "approver@customer.example",
        "approve": True,
        "rationale": "Should fail after payload change",
        "payload_hash_acknowledged": phash,
        "rollback_plan_acknowledged": True,
    })
    assert decide.status_code == 422
    pkg2 = await client.get(f"{API}/operation/{op_id}/approval-package", headers=headers)
    assert pkg2.json()["payload_hash"] == hash1


@pytest.mark.asyncio
async def test_rejection_blocks_operator_handoff(client):
    headers, org_id = await _headers_org(client, email="cp-rej@e.com", username="cprej", slug="cp-rej")
    op_id, _, phash = await _setup_pilot_op(client, headers, org_id)

    await client.post(f"{API}/operation/{op_id}/approval/decide", headers=headers, json={
        "approver_name": "Customer Approver",
        "approver_email": "approver@customer.example",
        "approve": False,
        "rationale": "Not ready",
        "payload_hash_acknowledged": phash,
        "rollback_plan_acknowledged": True,
    })

    handoff = await client.get(f"{PILOT}/live-operations/{op_id}/operator-handoff", headers=headers)
    assert handoff.status_code == 200
    assert handoff.json()["handoff_status"] in ("BLOCKED", "INSUFFICIENT_EVIDENCE")


@pytest.mark.asyncio
async def test_customer_approval_does_not_advance_execute(client):
    headers, org_id = await _headers_org(client, email="cp-exec@e.com", username="cpexec", slug="cp-exec")
    op_id, _, phash = await _setup_pilot_op(client, headers, org_id)

    await client.post(f"{API}/operation/{op_id}/approval/decide", headers=headers, json={
        "approver_name": "Customer Approver",
        "approver_email": "approver@customer.example",
        "approve": True,
        "rationale": "Approved",
        "payload_hash_acknowledged": phash,
        "rollback_plan_acknowledged": True,
    })

    from app.database.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        enrollment = (await session.execute(
            select(PilotEnrollment).where(PilotEnrollment.organization_id == org_id),
        )).scalar_one()
        stage = (await session.execute(
            select(PilotStage).where(
                PilotStage.enrollment_id == enrollment.id,
                PilotStage.stage_key == "EXECUTE",
            ),
        )).scalar_one_or_none()
        assert stage is None or stage.status != "COMPLETED"


@pytest.mark.asyncio
async def test_operator_handoff_read_only_rechecks(client):
    headers, org_id = await _headers_org(client, email="cp-hand@e.com", username="cphand", slug="cp-hand")
    op_id, _, phash = await _setup_pilot_op(client, headers, org_id)
    await client.post(f"{API}/operation/{op_id}/approval/decide", headers=headers, json={
        "approver_name": "Customer Approver",
        "approver_email": "approver@customer.example",
        "approve": True,
        "rationale": "Approved",
        "payload_hash_acknowledged": phash,
        "rollback_plan_acknowledged": True,
    })

    h1 = await client.get(f"{PILOT}/live-operations/{op_id}/operator-handoff", headers=headers)
    h2 = await client.get(f"{PILOT}/live-operations/{op_id}/operator-handoff", headers=headers)
    assert h1.status_code == 200
    assert h2.status_code == 200
    assert h1.json()["read_only"] is True
    assert "confirmation_token" not in json.dumps(h1.json())


@pytest.mark.asyncio
async def test_evidence_export_redacted(client):
    headers, org_id = await _headers_org(client, email="cp-exp@e.com", username="cpexp", slug="cp-exp")
    op_id, _, _ = await _setup_pilot_op(client, headers, org_id)

    export = await client.get(f"{API}/operation/{op_id}/evidence/export", headers=headers)
    assert export.status_code == 200
    body = export.text
    assert "ghp_" not in body
    data = export.json()
    assert data["redacted"] is True


def test_secret_scan_blocks_export():
    from app.pilot.customer_portal import assert_export_safe
    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        assert_export_safe({"token": "Bearer ghp_secret12345"})


@pytest.mark.asyncio
async def test_closeout_request_no_complete_transition(client):
    headers, org_id = await _headers_org(client, email="cp-close@e.com", username="cpclose", slug="cp-close")
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await _seed_checklist_complete(session, org_id)
        await session.commit()

    resp = await client.post(f"{API}/closeout/request", headers=headers, json={
        "signoff_contact": "lead@customer.example",
        "customer_comments": "Pilot complete",
        "documented_no_operation": True,
    })
    assert resp.status_code == 200
    assert resp.json()["request"]["status"] == "PENDING_OPERATOR_REVIEW"

    from app.database.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        complete = (await session.execute(
            select(func.count()).select_from(PilotStage).where(
                PilotStage.organization_id == org_id,
                PilotStage.stage_key == "COMPLETE",
                PilotStage.status == "COMPLETED",
            ),
        )).scalar_one()
        assert complete == 0


@pytest.mark.asyncio
async def test_no_internal_data_in_overview(client):
    headers, org_id = await _headers_org(client, email="cp-redact@e.com", username="cprd", slug="cp-redact")
    resp = await client.get(f"{API}/overview", headers=headers)
    blob = resp.text.lower()
    assert "41a17fb0" not in blob
    assert "nexora-pilot" not in blob
    assert "internal_non_production" not in blob


@pytest.mark.asyncio
async def test_notifications_deep_link_safe(client):
    headers, org_id = await _headers_org(client, email="cp-notif@e.com", username="cpnot", slug="cp-notif")
    op_id, _, phash = await _setup_pilot_op(client, headers, org_id)
    await client.post(f"{API}/operation/{op_id}/approval/decide", headers=headers, json={
        "approver_name": "Customer Approver",
        "approver_email": "approver@customer.example",
        "approve": True,
        "rationale": "Approved",
        "payload_hash_acknowledged": phash,
        "rollback_plan_acknowledged": True,
    })

    notes = await client.get(f"{API}/notifications", headers=headers)
    assert notes.status_code == 200
    for note in notes.json():
        assert note.get("action_url", "").startswith("/customer-pilot")
