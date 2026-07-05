"""Sprint 67E — Customer pilot deployment readiness tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.customer_pilot import PilotApprovalReminderDelivery
from app.models.pilot import PilotApproval
from app.pilot.backup_validation import validate_pg_backup_archive
from app.pilot.deployment_readiness import evaluate_pilot_deployment_readiness
from app.pilot.monitoring_rules import validate_customer_pilot_alert_rules
from app.pilot.operations_readiness import evaluate_pilot_operations_readiness
from app.services.customer_pilot_reminders import CustomerPilotReminderService
from app.tests.test_customer_pilot_portal import _headers_org, _setup_pilot_op

API = "/v1/customer-pilot"
PILOT = "/v1/pilot"


def _ops_payload(**overrides) -> dict:
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


def _deploy_payload(**overrides) -> dict:
    base = {
        "app_version": "1.0.0",
        "environment": "staging",
        "migration_head": "0039_customer_pilot_operations",
        "migration_current": "0039_customer_pilot_operations",
        "alembic_head_count": 1,
        "operations_payload": _ops_payload(),
        "pilot_mode_enabled": True,
        "pilot_mode_all_orgs": False,
        "pilot_organization_ids": ["41a17fb0-9d64-4e84-accf-0c81f6dc87c4"],
        "debug_enabled": False,
        "insecure_jwt_secret": False,
        "cors_origins": ["https://portal.example.com"],
        "rate_limit_enabled": True,
        "metrics_enabled": True,
        "health_ok": True,
        "health_detail": "database=pass",
        "email_notifications_enabled": False,
        "smtp_configured": False,
        "alert_receiver_configured": False,
        "backup_manifest_valid": True,
        "dry_run_completed": True,
        "dry_run_passed": True,
        "dry_run_detail": "passed",
    }
    base.update(overrides)
    return base


def test_deployment_readiness_go_with_insufficient_evidence_gaps():
    result = evaluate_pilot_deployment_readiness(_deploy_payload())
    assert result["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert "alert_receiver_not_configured" in result["insufficient_evidence"]
    assert "smtp_not_configured" not in result["insufficient_evidence"]


def test_deployment_readiness_no_go_migration():
    result = evaluate_pilot_deployment_readiness(_deploy_payload(
        migration_current="0038_customer_pilot_communications",
    ))
    assert result["verdict"] == "NO_GO"
    assert "migration_at_head" in result["failed_checks"]


def test_deployment_readiness_no_go_debug():
    result = evaluate_pilot_deployment_readiness(_deploy_payload(debug_enabled=True))
    assert result["verdict"] == "NO_GO"
    assert "debug_disabled" in result["failed_checks"]


def test_deployment_readiness_no_go_allowlist():
    result = evaluate_pilot_deployment_readiness(_deploy_payload(
        pilot_mode_all_orgs=True,
        pilot_organization_ids=[],
    ))
    assert result["verdict"] == "NO_GO"
    assert "pilot_org_allowlist" in result["failed_checks"]


def test_deployment_readiness_no_go_wildcard_cors():
    result = evaluate_pilot_deployment_readiness(_deploy_payload(cors_origins=["*"]))
    assert result["verdict"] == "NO_GO"
    assert "cors_not_wildcard" in result["failed_checks"]


def test_deployment_readiness_redis_degraded():
    result = evaluate_pilot_deployment_readiness(_deploy_payload(
        operations_payload=_ops_payload(redis_available=False),
    ))
    assert result["verdict"] == "NO_GO"
    assert any("ops_redis_connectivity" in c for c in result["failed_checks"])


def test_alert_rules_file_valid():
    result = validate_customer_pilot_alert_rules()
    assert result["valid"] is True
    assert "CustomerPilotSchedulerUnhealthy" in result["alerts_found"]


def test_backup_validation_missing_file():
    result = validate_pg_backup_archive("/nonexistent/path.dump")
    assert result["valid"] is False


@pytest.mark.asyncio
async def test_deployment_readiness_endpoint(client):
    headers, _ = await _headers_org(client, email="dep-rdy@e.com", username="deprdy", slug="dep-rdy")
    resp = await client.get(f"{PILOT}/deployment-readiness", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] in ("GO", "NO_GO", "INSUFFICIENT_EVIDENCE")
    assert data["read_only"] is True
    blob = resp.text.lower()
    assert "postgresql://" not in blob
    assert "password:" not in blob


@pytest.mark.asyncio
async def test_deployment_readiness_not_on_customer_api(client):
    headers, _ = await _headers_org(client, email="dep-cust@e.com", username="depcust", slug="dep-cust")
    resp = await client.get(f"{API}/readiness", headers=headers)
    assert resp.status_code == 200
    assert "deployment" not in resp.text.lower() or "operational_status" in resp.text


@pytest.mark.asyncio
async def test_dry_run_status_endpoint(client):
    headers, _ = await _headers_org(client, email="dry-st@e.com", username="dryst", slug="dry-st")
    resp = await client.get(f"{PILOT}/deployment-readiness/dry-run", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["internal_only"] is True


@pytest.mark.asyncio
async def test_reminder_idempotency_repeated_scheduler(client):
    from app.database.session import AsyncSessionLocal

    headers, org_id = await _headers_org(client, email="idem-67e@e.com", username="idem67e", slug="idem-67e")
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
                PilotApprovalReminderDelivery.reminder_type == "24H",
            ),
        )).scalars().all())
        assert len(deliveries) <= 1


@pytest.mark.asyncio
async def test_portal_dry_run_no_execution(client):
    headers, org_id = await _headers_org(client, email="dry-port@e.com", username="dryport", slug="dry-port")
    op_id, approval_id, _ = await _setup_pilot_op(client, headers, org_id)

    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        before = await session.get(PilotApproval, approval_id)
        before_status = before.status

    for path in (
        f"{API}/overview",
        f"{API}/timeline",
        f"{API}/readiness",
        f"{PILOT}/support/diagnostics",
        f"{PILOT}/deployment-readiness",
    ):
        resp = await client.get(path, headers=headers)
        assert resp.status_code == 200, path

    async with AsyncSessionLocal() as session:
        after = await session.get(PilotApproval, approval_id)
        assert after.status == before_status


@pytest.mark.asyncio
async def test_failure_drill_redis_no_go(client):
    headers, _ = await _headers_org(client, email="drill-redis@e.com", username="drillredis", slug="drill-redis")
    with patch(
        "app.services.pilot_operations.PilotOperationsService._redis_available",
        new=AsyncMock(return_value=False),
    ):
        ops = await client.get(f"{PILOT}/operations-readiness", headers=headers)
        dep = await client.get(f"{PILOT}/deployment-readiness", headers=headers)
    assert ops.json()["verdict"] == "NO_GO"
    assert dep.json()["verdict"] == "NO_GO"


@pytest.mark.asyncio
async def test_failure_drill_export_fail_closed():
    from app.core.exceptions import ValidationError
    from app.pilot.customer_portal import assert_export_safe

    with pytest.raises(ValidationError):
        assert_export_safe({"token": "password: supersecret"})


def test_operations_nested_in_deployment():
    ops = evaluate_pilot_operations_readiness(_ops_payload(redis_available=False))
    dep = evaluate_pilot_deployment_readiness(_deploy_payload(operations_payload=_ops_payload(redis_available=False)))
    assert ops["verdict"] == "NO_GO"
    assert dep["operations_verdict"] == "NO_GO"


@pytest.mark.asyncio
async def test_no_provider_mutation_deployment_endpoints(client):
    headers, org_id = await _headers_org(client, email="dep-safe@e.com", username="depsafe", slug="dep-safe")
    _, approval_id, _ = await _setup_pilot_op(client, headers, org_id)

    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        before = (await session.get(PilotApproval, approval_id)).status

    await client.get(f"{PILOT}/deployment-readiness", headers=headers)
    await client.get(f"{PILOT}/deployment-readiness/dry-run", headers=headers)

    async with AsyncSessionLocal() as session:
        after = (await session.get(PilotApproval, approval_id)).status
    assert before == after
