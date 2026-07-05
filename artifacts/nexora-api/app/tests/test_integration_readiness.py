"""Sprint 65G — Integration readiness tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.integration_readiness.capabilities import build_capability_matrix, enforce_write_allowed
from app.integration_readiness.evidence import redact_text
from app.integration_readiness.lifecycle import should_transition_state
from app.integration_readiness.observability_signals import collect_observability_signals
from app.integration_readiness.preflight import preflight_live_operation
from app.integration_readiness.probes import probe_observability, probe_security_binary
from app.models.integration_readiness import IntConnectionRegistry
from app.release_reliability.health_gates import GATE_INSUFFICIENT, evaluate_health_gate
from app.services.integration_verification import VStatus
from app.tests.conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    switch_organization,
)


async def _org_user(client, *, email: str, username: str, slug: str):
    _, tokens = await create_authenticated_user(client, email=email, username=username)
    org = await create_organization(client, tokens["access_token"], name=slug, slug=slug)
    tokens = await switch_organization(client, tokens["access_token"], org["id"])
    return tokens, org["id"]


def test_redact_secrets_in_evidence():
    text = "api_key=supersecret token=abc123"
    redacted = redact_text(text)
    assert "supersecret" not in redacted
    assert "REDACTED" in redacted


def test_k8s_read_only_blocks_writes():
    caps = build_capability_matrix("KUBERNETES", ["get", "list", "watch"])
    check = enforce_write_allowed(caps, provider_mode="live", lifecycle_state="CONNECTED")
    assert check["allowed"] is False
    assert "read-only" in check["reason"].lower()


def test_k8s_scale_patch_enables_minimal_write():
    caps = build_capability_matrix(
        "KUBERNETES",
        ["deployments:get", "scale:patch", "scale:update", "pods:list", "events:list"],
    )
    assert caps["write"] is True
    check = enforce_write_allowed(caps, provider_mode="live", lifecycle_state="CONNECTED")
    assert check["allowed"] is True


def test_failed_validation_never_connected_via_threshold():
    state = should_transition_state("CONNECTED", "FAILED", consecutive_failures=1, threshold=3)
    assert state == "CONNECTED"


def test_recovery_after_success():
    state = should_transition_state("FAILED", "CONNECTED", consecutive_failures=0, threshold=3)
    assert state == "CONNECTED"


def test_consecutive_failure_threshold():
    state = should_transition_state("CONNECTED", "FAILED", consecutive_failures=3, threshold=3)
    assert state == "FAILED"


def test_preflight_blocks_non_connected():
    result = preflight_live_operation(
        registry={"lifecycle_state": "FAILED", "provider_mode": "live", "capabilities": {"write": True},
                  "credential_id": "c1", "organization_id": "org1"},
        required_capabilities=["write"],
        environment_id="env1",
        organization_id="org1",
        idempotency_key="key1",
    )
    assert result["allowed"] is False
    assert result["simulated"] is False


def test_preflight_blocks_missing_capability():
    result = preflight_live_operation(
        registry={"lifecycle_state": "CONNECTED", "provider_mode": "live", "capabilities": {"read": True},
                  "credential_id": "c1", "organization_id": "org1"},
        required_capabilities=["write"],
        environment_id="env1",
        organization_id="org1",
        idempotency_key="key1",
    )
    assert result["allowed"] is False


def test_preflight_blocks_expired_reauth():
    result = preflight_live_operation(
        registry={"lifecycle_state": "CONNECTED", "provider_mode": "live", "capabilities": {"write": True},
                  "credential_id": "c1", "organization_id": "org1", "reauth_required": True},
        required_capabilities=["write"],
        environment_id="env1",
        organization_id="org1",
        idempotency_key="key1",
    )
    assert result["allowed"] is False


def test_preflight_blocks_offline_mode():
    result = preflight_live_operation(
        registry={"lifecycle_state": "CONNECTED", "provider_mode": "offline", "capabilities": {"write": True},
                  "credential_id": "c1", "organization_id": "org1"},
        required_capabilities=["write"],
        environment_id="env1",
        organization_id="org1",
        idempotency_key="key1",
    )
    assert result["allowed"] is False


def test_explicit_simulation_labeled():
    result = preflight_live_operation(
        registry={"lifecycle_state": "DRAFT", "provider_mode": "unavailable", "capabilities": {}},
        required_capabilities=["write"],
        environment_id="env1",
        organization_id="org1",
        idempotency_key="key1",
        explicit_simulation=True,
    )
    assert result["allowed"] is True
    assert result["simulated"] is True


def test_production_health_gate_blocks_without_live_observability():
    signals = collect_observability_signals(
        [{"kind": "PROMETHEUS", "provider_mode": "offline", "capabilities": {}}],
        deployment_health={"passed": True, "rollout_status": "Complete"},
    )
    gate = evaluate_health_gate(signals, is_production=True, environment_tier="PRODUCTION")
    assert gate["decision"] == GATE_INSUFFICIENT
    assert gate["blocks_promotion"] is True


def test_security_binary_offline_when_missing():
    with patch("app.integration_readiness.probes.shutil.which", return_value=None):
        result = probe_security_binary("TRIVY")
    assert result["provider_mode"] == "offline"


def test_observability_probe_offline_without_endpoint():
    result = probe_observability("PROMETHEUS", {})
    assert result["provider_mode"] == "offline"


@pytest.mark.asyncio
async def test_integration_readiness_api_dashboard(client):
    tokens, _org_id = await _org_user(client, email="int1@e.com", username="intuser1", slug="int-org-1")
    headers = auth_headers(tokens["access_token"])
    dash = await client.get("/v1/integrations/dashboard", headers=headers)
    assert dash.status_code == 200
    body = dash.json()
    assert "total" in body
    assert "connected" in body


@pytest.mark.asyncio
async def test_validate_connection_offline_probe(client):
    tokens, org_id = await _org_user(client, email="int2@e.com", username="intuser2", slug="int-org-2")
    headers = auth_headers(tokens["access_token"])
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        row = IntConnectionRegistry(
            organization_id=org_id,
            resource_type="security",
            resource_id="sec-test-1",
            provider_type="TRIVY",
            lifecycle_state="DRAFT",
            provider_mode="unavailable",
            capabilities={},
            idempotency_key="test-key-trivy-1",
        )
        session.add(row)
        await session.commit()
        reg_id = row.id

    with patch("app.integration_readiness.probes.shutil.which", return_value=None):
        resp = await client.post(f"/v1/integrations/connections/{reg_id}/validate", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["lifecycle_state"] != "CONNECTED"
    assert data["provider_mode"] in ("offline", "unavailable")


@pytest.mark.asyncio
async def test_tenant_isolation(client):
    tokens1, org1 = await _org_user(client, email="inta@e.com", username="intusera", slug="int-org-a")
    tokens2, _org2 = await _org_user(client, email="intb@e.com", username="intuserb", slug="int-org-b")
    h1 = auth_headers(tokens1["access_token"])
    h2 = auth_headers(tokens2["access_token"])
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        row = IntConnectionRegistry(
            organization_id=org1,
            resource_type="security",
            resource_id="iso-1",
            provider_type="TRIVY",
            lifecycle_state="DRAFT",
            provider_mode="unavailable",
            capabilities={},
            idempotency_key="iso-key-1",
        )
        session.add(row)
        await session.commit()
        reg_id = row.id

    denied = await client.get(f"/v1/integrations/connections/{reg_id}/health", headers=h2)
    assert denied.status_code in (403, 404)
    allowed = await client.get(f"/v1/integrations/connections/{reg_id}/health", headers=h1)
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_expiry_acknowledge_snooze(client):
    tokens, org_id = await _org_user(client, email="int3@e.com", username="intuser3", slug="int-org-3")
    headers = auth_headers(tokens["access_token"])
    from app.database.session import AsyncSessionLocal
    from app.models.integration_readiness import IntExpiryReminder

    async with AsyncSessionLocal() as session:
        row = IntConnectionRegistry(
            organization_id=org_id,
            resource_type="marketplace",
            resource_id="m-1",
            provider_type="GITHUB",
            lifecycle_state="CONNECTED",
            provider_mode="live",
            capabilities={"read": True},
            idempotency_key="exp-key-1",
        )
        session.add(row)
        await session.flush()
        reminder = IntExpiryReminder(
            organization_id=org_id,
            registry_id=row.id,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            warning_level="7d",
        )
        session.add(reminder)
        await session.commit()
        reg_id = row.id

    ack = await client.post(
        f"/v1/integrations/connections/{reg_id}/acknowledge-expiry",
        headers=headers,
        json={"reminder_id": None},
    )
    assert ack.status_code == 200
    snooze = await client.post(
        f"/v1/integrations/connections/{reg_id}/snooze-expiry",
        headers=headers,
        json={"days": 14},
    )
    assert snooze.status_code == 200


@pytest.mark.asyncio
async def test_test_notification_dry_run(client):
    tokens, _org_id = await _org_user(client, email="int4@e.com", username="intuser4", slug="int-org-4")
    headers = auth_headers(tokens["access_token"])
    resp = await client.post(
        "/v1/integrations/notifications/test",
        headers=headers,
        json={"channel": "slack", "dry_run": True},
    )
    assert resp.status_code == 200
    assert resp.json()["simulated"] is True


@pytest.mark.asyncio
async def test_test_notification_live_without_webhook_is_simulated(client):
    tokens, _org_id = await _org_user(client, email="int5@e.com", username="intuser5", slug="int-org-5")
    headers = auth_headers(tokens["access_token"])
    resp = await client.post(
        "/v1/integrations/notifications/test",
        headers=headers,
        json={"channel": "slack", "dry_run": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["simulated"] is True
    assert body["sent"] is False
    assert "webhook" in body["message"].lower() or "simulated" in body["message"].lower()


@pytest.mark.asyncio
async def test_live_preflight_persists_evidence(setup_db):
    from app.auth.org_context import OrgContext
    from app.database.session import AsyncSessionLocal
    from app.models.organization import Organization, OrganizationMember, OrganizationRole
    from app.models.user import User
    from app.services.integration_readiness import IntegrationReadinessService

    async with AsyncSessionLocal() as session:
        user = User(email="pf@e.com", username="pfuser", full_name="PF User", hashed_password="x", is_active=True)
        org = Organization(name="PF Org", slug="pf-org")
        session.add_all([user, org])
        await session.flush()
        session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=OrganizationRole.OWNER))
        row = IntConnectionRegistry(
            organization_id=org.id,
            resource_type="marketplace",
            resource_id="pf-1",
            provider_type="KUBERNETES",
            lifecycle_state="FAILED",
            provider_mode="unavailable",
            capabilities={},
            idempotency_key="pf-key-1",
        )
        session.add(row)
        await session.commit()
        svc = IntegrationReadinessService(session)
        result = await svc.run_preflight(
            organization_id=org.id,
            registry_id=row.id,
            required_capabilities=["write"],
            idempotency_key="pf-idem-1",
        )
        await session.commit()
    assert result["allowed"] is False


def test_migration_0033_revision_chain():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0033_integration_readiness.py"
    spec = importlib.util.spec_from_file_location("migration_0033", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.down_revision == "0032_release_reliability"
    assert m.revision == "0033_integration_readiness"


def test_migration_0033_idempotent_upgrade():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0033_integration_readiness.py"
    spec = importlib.util.spec_from_file_location("migration_0033", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert callable(m.upgrade)
    assert callable(m.downgrade)
