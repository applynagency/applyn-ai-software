"""Sprint 67C — Customer pilot communications, timeline, reminders tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.customer_pilot import PilotApprovalReminderDelivery, PilotCustomerCommunication
from app.models.pilot import PilotApproval
from app.models.user import User
from app.pilot.customer_portal import assert_export_safe
from app.services.customer_pilot_reminders import CustomerPilotReminderService
from app.tests.conftest import auth_headers, create_authenticated_user
from app.tests.test_customer_pilot_portal import _headers_org, _setup_pilot_op
from app.tests.test_pilot_readiness import _seed_checklist_complete

API = "/v1/customer-pilot"
PILOT = "/v1/pilot"


@pytest.mark.asyncio
async def test_timeline_events_and_pagination(client):
    headers, _ = await _headers_org(client, email="tl-1@e.com", username="tl1", slug="tl-1")
    resp = await client.get(f"{API}/timeline", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert "stage_summary" in data


@pytest.mark.asyncio
async def test_timeline_no_internal_audit(client):
    headers, org_id = await _headers_org(client, email="tl-red@e.com", username="tlred", slug="tl-red")
    from app.database.session import AsyncSessionLocal
    from app.repositories.audit import AuditLogRepository

    async with AsyncSessionLocal() as session:
        audit = AuditLogRepository(session)
        await audit.log(
            action="pilot.confirmation_token_issued",
            resource_type="pilot_live_operation",
            resource_id="secret-op",
            organization_id=org_id,
            details={"confirmation_token": "ghp_secret", "kubeconfig": "secret"},
        )
        await session.commit()

    resp = await client.get(f"{API}/timeline", headers=headers)
    blob = resp.text.lower()
    assert "confirmation_token" not in blob
    assert "ghp_" not in blob


@pytest.mark.asyncio
async def test_timeline_export_redaction(client):
    headers, _ = await _headers_org(client, email="tl-exp@e.com", username="tlexp", slug="tl-exp")
    export = await client.get(f"{API}/timeline/export", headers=headers)
    assert export.status_code == 200
    assert export.json()["redacted"] is True


def test_timeline_export_secret_block():
    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        assert_export_safe({"token": "password: supersecret"})


@pytest.mark.asyncio
async def test_tenant_isolation_timeline(client):
    h1, org1 = await _headers_org(client, email="tl-iso1@e.com", username="tliso1", slug="tl-iso1")
    h2, _ = await _headers_org(client, email="tl-iso2@e.com", username="tliso2", slug="tl-iso2")
    await _setup_pilot_op(client, h1, org1)
    r1 = await client.get(f"{API}/timeline", headers=h1)
    r2 = await client.get(f"{API}/timeline", headers=h2)
    ids1 = {e.get("operation_id") for e in r1.json().get("events", []) if e.get("operation_id")}
    ids2 = {e.get("operation_id") for e in r2.json().get("events", []) if e.get("operation_id")}
    assert ids1.isdisjoint(ids2) or not ids1


@pytest.mark.asyncio
async def test_approval_reminder_dedup(client):
    from app.database.session import AsyncSessionLocal

    headers, org_id = await _headers_org(client, email="rem-1@e.com", username="rem1", slug="rem-1")
    _, approval_id, _ = await _setup_pilot_op(client, headers, org_id)

    async with AsyncSessionLocal() as session:
        approval = await session.get(PilotApproval, approval_id)
        approval.expires_at = datetime.now(UTC) + timedelta(hours=23, minutes=30)
        await session.commit()

    with patch("app.services.customer_pilot_reminders.scheduler_lock") as mock_lock:
        mock_lock.return_value.__aenter__.return_value = "token"
        async with AsyncSessionLocal() as session:
            svc = CustomerPilotReminderService(session)
            await svc.run()
            await svc.run()
            await session.commit()

    async with AsyncSessionLocal() as session:
        deliveries = list((await session.execute(
            select(PilotApprovalReminderDelivery).where(
                PilotApprovalReminderDelivery.approval_id == approval_id,
            ),
        )).scalars().all())
        types = [d.reminder_type for d in deliveries]
        assert types.count("24H") <= 1


@pytest.mark.asyncio
async def test_no_reminder_after_approval(client):
    from app.database.session import AsyncSessionLocal

    headers, org_id = await _headers_org(client, email="rem-ap@e.com", username="remap", slug="rem-ap")
    op_id, approval_id, phash = await _setup_pilot_op(client, headers, org_id)
    await client.post(f"{API}/operation/{op_id}/approval/decide", headers=headers, json={
        "approver_name": "A", "approver_email": "approver@customer.example",
        "approve": True, "rationale": "ok",
        "payload_hash_acknowledged": phash, "rollback_plan_acknowledged": True,
    })

    async with AsyncSessionLocal() as session:
        approval = await session.get(PilotApproval, approval_id)
        approval.expires_at = datetime.now(UTC) + timedelta(minutes=30)
        await session.commit()

    with patch("app.services.customer_pilot_reminders.scheduler_lock") as mock_lock:
        mock_lock.return_value.__aenter__.return_value = "token"
        async with AsyncSessionLocal() as session:
            result = await CustomerPilotReminderService(session).run()
            await session.commit()

    assert result.get("sent_1h", 0) == 0


@pytest.mark.asyncio
async def test_notification_preferences(client):
    headers, _ = await _headers_org(client, email="pref-1@e.com", username="pref1", slug="pref-1")
    get0 = await client.get(f"{API}/notification-preferences", headers=headers)
    assert get0.status_code == 200
    assert get0.json()["approval_reminders_enabled"] is True

    put = await client.put(f"{API}/notification-preferences", headers=headers, json={
        "approval_reminders_enabled": False,
        "timezone": "America/New_York",
    })
    assert put.status_code == 200
    assert put.json()["approval_reminders_enabled"] is False


@pytest.mark.asyncio
async def test_operator_communication_draft_send(client):
    headers, org_id = await _headers_org(client, email="comm-op@e.com", username="commop", slug="comm-op")
    from app.database.session import AsyncSessionLocal
    from app.models.organization import OrganizationMember

    async with AsyncSessionLocal() as session:
        await _seed_checklist_complete(session, org_id)
        user = (await session.execute(select(User).limit(1))).scalar_one()
        recipient_id = user.id
        await session.commit()

    draft = await client.post(f"{PILOT}/communications/draft", headers=headers, json={
        "category": "PILOT_STATUS_UPDATE",
        "recipient_user_ids": [recipient_id],
        "title": "Pilot update",
        "body": "Your pilot readiness review is progressing.",
    })
    assert draft.status_code == 200
    comm_id = draft.json()["id"]

    sent = await client.post(f"{PILOT}/communications/{comm_id}/send", headers=headers)
    assert sent.status_code == 200
    assert sent.json()["status"] == "SENT"

    listed = await client.get(f"{API}/communications", headers=headers)
    assert any(c["id"] == comm_id for c in listed.json())

    ack = await client.post(f"{API}/communications/{comm_id}/acknowledge", headers=headers)
    assert ack.status_code == 200


@pytest.mark.asyncio
async def test_operator_message_blocks_false_verified_claim(client):
    headers, org_id = await _headers_org(client, email="comm-guard@e.com", username="commg", slug="comm-guard")
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await _seed_checklist_complete(session, org_id)
        user = (await session.execute(select(User).limit(1))).scalar_one()
        recipient_id = user.id
        await session.commit()

    bad = await client.post(f"{PILOT}/communications/draft", headers=headers, json={
        "category": "VERIFICATION_UPDATE",
        "recipient_user_ids": [recipient_id],
        "body": "Operation verified successfully and execution succeeded.",
    })
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_customer_comment_rate_limit(client):
    headers, org_id = await _headers_org(client, email="cmt-1@e.com", username="cmt1", slug="cmt-1")
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await _seed_checklist_complete(session, org_id)
        row = PilotCustomerCommunication(
            organization_id=org_id,
            category="PILOT_STATUS_UPDATE",
            status="SENT",
            title="t",
            body="b",
            created_by="x",
            recipient_user_ids=[],
            acknowledgements=[],
            sent_at=datetime.now(UTC),
        )
        session.add(row)
        await session.flush()
        comm_id = row.id
        await session.commit()

    last = None
    for i in range(11):
        last = await client.post(f"{API}/communications/{comm_id}/comment", headers=headers, json={
            "body": f"comment {i}",
        })
    assert last.status_code == 422
