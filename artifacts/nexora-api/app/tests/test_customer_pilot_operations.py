"""Sprint 67D — Customer pilot operations reliability tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.customer_pilot import PilotNotificationDelivery, PilotSchedulerHealthSnapshot
from app.models.job import Job, JobType
from app.models.pilot import PilotApproval
from app.pilot.customer_portal import assert_export_safe
from app.pilot.operations_readiness import (
    customer_safe_operations_status,
    evaluate_pilot_operations_readiness,
)
from app.services.pilot_notification_delivery import PilotNotificationDeliveryService
from app.tests.test_customer_pilot_portal import _headers_org, _setup_pilot_op

API = "/v1/customer-pilot"
PILOT = "/v1/pilot"


def _healthy_payload(**overrides) -> dict:
    base = {
        "redis_available": True,
        "worker_recent": True,
        "worker_detail": "ok",
        "reminder_cron_registered": True,
        "job_queue_enabled": True,
        "distributed_lock_enabled": True,
        "scheduler_lock_available": True,
        "scheduler_lock_detail": "ok",
        "reminder_last_success_at": datetime.now(UTC).isoformat(),
        "reminder_consecutive_failures": 0,
        "reminder_stale_hours": 24,
        "notification_queue_oldest_seconds": 10,
        "failed_delivery_count": 0,
        "clock_sane": True,
        "email_configured": True,
    }
    base.update(overrides)
    return base


def test_operations_readiness_go():
    result = evaluate_pilot_operations_readiness(_healthy_payload())
    assert result["verdict"] == "GO"
    assert not result["failed_checks"]


def test_operations_readiness_no_go_redis():
    result = evaluate_pilot_operations_readiness(_healthy_payload(redis_available=False))
    assert result["verdict"] == "NO_GO"
    assert "redis_connectivity" in result["failed_checks"]
    assert any("Redis" in s for s in result["remediation_steps"])


def test_operations_readiness_insufficient_evidence():
    result = evaluate_pilot_operations_readiness(_healthy_payload(
        reminder_last_success_at=None,
        worker_recent=True,
    ))
    assert result["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_operations_readiness_worker_unavailable():
    result = evaluate_pilot_operations_readiness(_healthy_payload(
        worker_recent=False,
        worker_detail="No worker",
        job_queue_enabled=True,
    ))
    assert result["verdict"] == "NO_GO"
    assert "arq_worker_heartbeat" in result["failed_checks"]


def test_operations_readiness_stale_cron():
    old = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
    result = evaluate_pilot_operations_readiness(_healthy_payload(
        reminder_last_success_at=old,
        reminder_stale_hours=1,
    ))
    assert result["verdict"] == "NO_GO"
    assert "reminder_last_success" in result["failed_checks"]


def test_customer_safe_operations_status_no_infra_names():
    ops = evaluate_pilot_operations_readiness(_healthy_payload(redis_available=False))
    safe = customer_safe_operations_status(ops)
    assert "redis" not in str(safe).lower()
    assert "arq" not in str(safe).lower()
    assert safe["notifications_operational"] == "degraded"
    assert safe["degradation_notice"]


@pytest.mark.asyncio
async def test_operations_readiness_endpoint(client):
    headers, _ = await _headers_org(client, email="ops-rdy@e.com", username="opsrdy", slug="ops-rdy")
    resp = await client.get(f"{PILOT}/operations-readiness", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] in ("GO", "NO_GO", "INSUFFICIENT_EVIDENCE")
    assert data["read_only"] is True
    assert "checks" in data


@pytest.mark.asyncio
async def test_customer_readiness_operational_status(client):
    headers, _ = await _headers_org(client, email="ops-cust@e.com", username="opscust", slug="ops-cust")
    resp = await client.get(f"{API}/readiness", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "operational_status" in data
    ops = data["operational_status"]
    assert "notifications_operational" in ops
    assert "approval_reminders_operational" in ops
    assert "support_monitoring_operational" in ops
    blob = resp.text.lower()
    assert "smtp" not in blob
    assert "redis" not in blob


@pytest.mark.asyncio
async def test_notification_delivery_idempotency(client):
    from app.database.session import AsyncSessionLocal

    headers, org_id = await _headers_org(client, email="del-idem@e.com", username="delidem", slug="del-idem")
    user_resp = await client.get("/v1/auth/me", headers=headers)
    user_id = user_resp.json()["id"]

    async with AsyncSessionLocal() as session:
        svc = PilotNotificationDeliveryService(session)
        d1 = await svc.deliver_in_app(
            organization_id=org_id,
            user_id=user_id,
            title="Test",
            body="Body",
            action_url="/customer-pilot",
            idempotency_key="test:idem:1",
        )
        d2 = await svc.deliver_in_app(
            organization_id=org_id,
            user_id=user_id,
            title="Test",
            body="Body",
            action_url="/customer-pilot",
            idempotency_key="test:idem:1",
        )
        await session.commit()
        assert d1.id == d2.id
        rows = list((await session.execute(
            select(PilotNotificationDelivery).where(
                PilotNotificationDelivery.idempotency_key == "test:idem:1",
            ),
        )).scalars().all())
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_notification_bounded_retry_no_duplicate(client):
    from app.database.session import AsyncSessionLocal

    headers, org_id = await _headers_org(client, email="del-retry@e.com", username="delretry", slug="del-retry")
    user_id = (await client.get("/v1/auth/me", headers=headers)).json()["id"]

    async with AsyncSessionLocal() as session:
        svc = PilotNotificationDeliveryService(session)
        delivery = await svc.get_or_create(
            organization_id=org_id,
            recipient_user_id=user_id,
            channel="email",
            idempotency_key="retry:test:1",
        )
        for _ in range(6):
            await svc.mark_failed(delivery, "smtp error")
            await session.refresh(delivery)
        await session.commit()
        assert delivery.status == "failed"
        assert delivery.attempts >= delivery.max_attempts


@pytest.mark.asyncio
async def test_suppressed_preference_delivery(client):
    from app.database.session import AsyncSessionLocal
    from app.models.customer_pilot import PilotNotificationPreference

    headers, org_id = await _headers_org(client, email="del-sup@e.com", username="delsup", slug="del-sup")
    user_id = (await client.get("/v1/auth/me", headers=headers)).json()["id"]

    async with AsyncSessionLocal() as session:
        session.add(PilotNotificationPreference(
            organization_id=org_id,
            user_id=user_id,
            in_app_enabled=False,
            email_enabled=False,
            approval_reminders_enabled=False,
            evidence_ready_enabled=True,
            closeout_notifications_enabled=True,
            timezone="UTC",
        ))
        await session.commit()

    async with AsyncSessionLocal() as session:
        svc = PilotNotificationDeliveryService(session)
        d = await svc.deliver_in_app(
            organization_id=org_id,
            user_id=user_id,
            title="Suppressed",
            body="Body",
            action_url="/customer-pilot",
            idempotency_key="sup:test:1",
            suppressed=True,
        )
        await session.commit()
        assert d.status == "suppressed_by_preference"


@pytest.mark.asyncio
async def test_requeue_failed_only_and_audit(client):
    from app.database.session import AsyncSessionLocal

    headers, org_id = await _headers_org(client, email="requeue-1@e.com", username="requeue1", slug="requeue-1")
    _, approval_id, _ = await _setup_pilot_op(client, headers, org_id)
    comm_id = "comm-test-1"
    delivery_id = None

    async with AsyncSessionLocal() as session:
        delivery = PilotNotificationDelivery(
            organization_id=org_id,
            communication_id=comm_id,
            approval_id=approval_id,
            recipient_user_id="user-1",
            channel="email",
            status="failed",
            idempotency_key="requeue:test:1",
            queued_at=datetime.now(UTC),
        )
        session.add(delivery)
        await session.flush()
        delivery_id = delivery.id
        await session.commit()

    bad = await client.post(
        f"{PILOT}/communications/{comm_id}/deliveries/{delivery_id}/requeue",
        headers=headers,
    )
    assert bad.status_code == 200
    data = bad.json()
    assert data["status"] == "queued"

    again = await client.post(
        f"{PILOT}/communications/{comm_id}/deliveries/{delivery_id}/requeue",
        headers=headers,
    )
    assert again.status_code == 200
    assert again.json().get("idempotent") is True

    async with AsyncSessionLocal() as session:
        approval = await session.get(PilotApproval, approval_id)
        assert approval.status == "PENDING"


@pytest.mark.asyncio
async def test_requeue_blocked_non_pending_approval(client):
    from app.database.session import AsyncSessionLocal

    headers, org_id = await _headers_org(client, email="requeue-exp@e.com", username="requeueexp", slug="requeue-exp")
    _, approval_id, _ = await _setup_pilot_op(client, headers, org_id)
    comm_id = "comm-exp-1"

    async with AsyncSessionLocal() as session:
        approval = await session.get(PilotApproval, approval_id)
        approval.status = "EXPIRED"
        delivery = PilotNotificationDelivery(
            organization_id=org_id,
            communication_id=comm_id,
            approval_id=approval_id,
            recipient_user_id="user-1",
            channel="email",
            status="failed",
            idempotency_key="requeue:exp:1",
            queued_at=datetime.now(UTC),
        )
        session.add(delivery)
        await session.flush()
        delivery_id = delivery.id
        await session.commit()

    resp = await client.post(
        f"{PILOT}/communications/{comm_id}/deliveries/{delivery_id}/requeue",
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_requeue_sent_delivery_rejected(client):
    from app.database.session import AsyncSessionLocal

    headers, org_id = await _headers_org(client, email="requeue-sent@e.com", username="requeuesent", slug="requeue-sent")
    comm_id = "comm-sent-1"

    async with AsyncSessionLocal() as session:
        delivery = PilotNotificationDelivery(
            organization_id=org_id,
            communication_id=comm_id,
            recipient_user_id="user-1",
            channel="in_app",
            status="delivered",
            idempotency_key="requeue:sent:1",
            queued_at=datetime.now(UTC),
        )
        session.add(delivery)
        await session.flush()
        delivery_id = delivery.id
        await session.commit()

    resp = await client.post(
        f"{PILOT}/communications/{comm_id}/deliveries/{delivery_id}/requeue",
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_support_bundle_tenant_isolation(client):
    h1, org1 = await _headers_org(client, email="bundle-1@e.com", username="bundle1", slug="bundle-1")
    h2, _ = await _headers_org(client, email="bundle-2@e.com", username="bundle2", slug="bundle-2")
    await _setup_pilot_op(client, h1, org1)

    b1 = await client.get(f"{PILOT}/support/diagnostics/export", headers=h1)
    b2 = await client.get(f"{PILOT}/support/diagnostics/export", headers=h2)
    assert b1.status_code == 200
    assert b2.status_code == 200
    org1_name = b1.json()["json"]["organization_name"]
    org2_name = b2.json()["json"]["organization_name"]
    assert org1_name != org2_name


@pytest.mark.asyncio
async def test_support_bundle_redaction_fail_closed():
    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        assert_export_safe({"token": "password: supersecret"})


@pytest.mark.asyncio
async def test_support_diagnostics_enriched(client):
    headers, _ = await _headers_org(client, email="diag-en@e.com", username="digen", slug="diag-en")
    resp = await client.get(f"{PILOT}/support/diagnostics", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "operations_readiness" in data
    assert "notification_health" in data


@pytest.mark.asyncio
async def test_scheduler_health_snapshot_recorded(client):
    from app.database.session import AsyncSessionLocal
    from app.services.customer_pilot_reminders import run_customer_pilot_approval_reminders

    with patch("app.services.customer_pilot_reminders.scheduler_lock") as mock_lock:
        mock_lock.return_value.__aenter__.return_value = "token"
        async with AsyncSessionLocal() as session:
            await run_customer_pilot_approval_reminders(session)

    async with AsyncSessionLocal() as session:
        snap = (await session.execute(
            select(PilotSchedulerHealthSnapshot).where(
                PilotSchedulerHealthSnapshot.job_type == JobType.CRON_CUSTOMER_PILOT_APPROVAL_REMINDERS.value,
            ).order_by(PilotSchedulerHealthSnapshot.ran_at.desc()).limit(1),
        )).scalar_one_or_none()
        assert snap is not None


@pytest.mark.asyncio
async def test_operations_readiness_redis_degraded(client):
    headers, _ = await _headers_org(client, email="ops-redis@e.com", username="opsredis", slug="ops-redis")
    with patch(
        "app.services.pilot_operations.PilotOperationsService._redis_available",
        new=AsyncMock(return_value=False),
    ):
        resp = await client.get(f"{PILOT}/operations-readiness", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["verdict"] == "NO_GO"


@pytest.mark.asyncio
async def test_no_provider_mutation_from_operations_endpoints(client):
    headers, org_id = await _headers_org(client, email="ops-safe@e.com", username="opssafe", slug="ops-safe")
    op_id, _, _ = await _setup_pilot_op(client, headers, org_id)

    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        before = (await session.execute(
            select(PilotApproval).where(PilotApproval.organization_id == org_id),
        )).scalars().all()
        before_status = {a.id: a.status for a in before}

    await client.get(f"{PILOT}/operations-readiness", headers=headers)
    await client.get(f"{PILOT}/support/diagnostics", headers=headers)
    await client.get(f"{PILOT}/support/diagnostics/export", headers=headers)

    async with AsyncSessionLocal() as session:
        after = (await session.execute(
            select(PilotApproval).where(PilotApproval.organization_id == org_id),
        )).scalars().all()
        after_status = {a.id: a.status for a in after}
    assert before_status == after_status
