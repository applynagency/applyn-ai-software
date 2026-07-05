"""Sprint 67A — Customer integration onboarding tests."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select

from app.integration_readiness.evidence import redact_text
from app.models.integration_onboarding import IntegrationOnboardingSession
from app.models.integration_readiness import IntConnectionRegistry
from app.models.pilot import PilotApproval, PilotEnrollment, PilotLiveOperation, PilotStage
from app.tests.conftest import auth_headers, create_authenticated_user, create_organization, switch_organization

API = "/v1/onboarding/integrations"


async def _admin_client(client):
    user, tokens = await create_authenticated_user(
        client, email="onboard-admin@e.com", username="onboardadmin", password="Pass123!",
    )
    org = await create_organization(client, tokens["access_token"], name="Onboard Org", slug="onboard-org")
    switched = await switch_organization(client, tokens["access_token"], org["id"])
    headers = auth_headers(switched["access_token"])
    return headers, org["id"], user["id"]


K8S_OK = {
    "ok": True,
    "status": "VALIDATED",
    "provider_mode": "live",
    "read_checks": [{"permission": "apps/deployments:get", "allowed": True}],
    "scale_checks": [{"permission": "apps/deployments/scale:patch", "allowed": True}],
    "prohibited_granted": [],
    "rbac_gaps": [],
    "inventory": {"namespace": "pilot-ns", "deployments": [{"name": "api"}], "pods": []},
    "capabilities": {"read": True, "kubernetes.workloads.write": True},
    "evidence_refs": {"namespace": "pilot-ns", "deployment_count": 1, "pod_count": 0},
}

GITHUB_OK = {
    "ok": True,
    "status": "VALIDATED",
    "provider_mode": "live",
    "connection_status": "CONNECTED",
    "capabilities": {"read": True, "repository_access": True, "workflow_history": False},
    "missing_capabilities": [],
    "insufficient_evidence": ["workflow_history_unavailable"],
    "provider_identity": {"login": "customer-bot"},
    "errors": [],
    "warnings": [],
    "evidence_refs": {"repository": "org/repo"},
}

PROM_OK = {
    "ok": True,
    "status": "VALIDATED",
    "provider_mode": "live",
    "capabilities": {"query_metrics": True, "read": True},
    "missing_capabilities": [],
    "insufficient_evidence": [],
    "errors": [],
    "warnings": [],
    "evidence_refs": {"endpoint_host": "prom.example", "targets_up": 1},
}


@pytest.mark.asyncio
async def test_list_providers(client):
    headers, _, _ = await _admin_client(client)
    resp = await client.get(f"{API}/providers", headers=headers)
    assert resp.status_code == 200
    providers = {p["provider_type"] for p in resp.json()}
    assert "KUBERNETES" in providers
    assert "PROMETHEUS" in providers


@pytest.mark.asyncio
async def test_production_environment_rejected(client):
    headers, _, _ = await _admin_client(client)
    created = await client.post(f"{API}/sessions", headers=headers, json={"provider_type": "KUBERNETES"})
    sid = created.json()["id"]
    resp = await client.put(
        f"{API}/sessions/{sid}/environment",
        headers=headers,
        json={
            "environment_name": "prod",
            "environment_classification": "production",
            "scope": {"namespace": "app"},
            "intended_for_pilot": True,
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_kubernetes_wildcard_namespace_rejected(client):
    headers, _, _ = await _admin_client(client)
    sid = (await client.post(f"{API}/sessions", headers=headers, json={"provider_type": "KUBERNETES"})).json()["id"]
    resp = await client.put(
        f"{API}/sessions/{sid}/environment",
        headers=headers,
        json={
            "environment_name": "staging",
            "environment_classification": "staging",
            "scope": {"namespace": "*"},
            "intended_for_pilot": True,
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_kubernetes_cluster_wide_scope_rejected(client):
    headers, _, _ = await _admin_client(client)
    sid = (await client.post(f"{API}/sessions", headers=headers, json={"provider_type": "KUBERNETES"})).json()["id"]
    resp = await client.put(
        f"{API}/sessions/{sid}/environment",
        headers=headers,
        json={
            "environment_name": "staging",
            "environment_classification": "staging",
            "scope": {"namespace": "cluster-wide"},
            "intended_for_pilot": True,
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_kubernetes_successful_validation_creates_live_connection(client):
    headers, org_id, _ = await _admin_client(client)
    sid = (await client.post(f"{API}/sessions", headers=headers, json={"provider_type": "KUBERNETES"})).json()["id"]
    await client.put(
        f"{API}/sessions/{sid}/environment",
        headers=headers,
        json={
            "environment_name": "staging",
            "environment_classification": "staging",
            "scope": {"namespace": "pilot-ns", "cluster_endpoint": "cluster-a"},
            "intended_for_pilot": True,
        },
    )
    await client.post(
        f"{API}/sessions/{sid}/credentials",
        headers=headers,
        json={"name": "k8s-cred", "secret": {"kubeconfig": "apiVersion: v1\nclusters: []\n"}},
    )
    with patch(
        "app.services.integration_onboarding.validate_kubernetes",
        new_callable=AsyncMock,
        return_value=K8S_OK,
    ):
        result = await client.post(f"{API}/sessions/{sid}/validate", headers=headers)
    assert result.status_code == 200
    body = result.json()
    assert body["status"] == "VALIDATED"
    assert body["registry_connection_id"]

    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        reg = await session.get(IntConnectionRegistry, body["registry_connection_id"])
        assert reg.lifecycle_state == "CONNECTED"
        assert reg.provider_mode == "live"
        assert reg.organization_id == org_id


@pytest.mark.asyncio
async def test_kubernetes_prohibited_permission_fails(client):
    headers, _, _ = await _admin_client(client)
    sid = (await client.post(f"{API}/sessions", headers=headers, json={"provider_type": "KUBERNETES"})).json()["id"]
    await client.put(
        f"{API}/sessions/{sid}/environment",
        headers=headers,
        json={
            "environment_name": "staging",
            "environment_classification": "staging",
            "scope": {"namespace": "pilot-ns"},
            "intended_for_pilot": True,
        },
    )
    await client.post(
        f"{API}/sessions/{sid}/credentials",
        headers=headers,
        json={"name": "k8s-cred", "secret": {"kubeconfig": "apiVersion: v1\n"}},
    )
    bad = {**K8S_OK, "ok": False, "prohibited_granted": ["core/secrets:get"]}
    with patch(
        "app.services.integration_onboarding.validate_kubernetes",
        new_callable=AsyncMock,
        return_value=bad,
    ):
        result = await client.post(f"{API}/sessions/{sid}/validate", headers=headers)
    assert result.status_code == 200
    assert result.json()["status"] == "FAILED"
    assert result.json()["registry_connection_id"] is None


@pytest.mark.asyncio
async def test_failed_validation_no_live_connection(client):
    headers, org_id, _ = await _admin_client(client)
    sid = (await client.post(f"{API}/sessions", headers=headers, json={"provider_type": "PROMETHEUS"})).json()["id"]
    await client.put(
        f"{API}/sessions/{sid}/environment",
        headers=headers,
        json={
            "environment_name": "staging",
            "environment_classification": "staging",
            "scope": {"namespace_label": "namespace", "namespace_label_value": "pilot-ns"},
            "intended_for_pilot": True,
        },
    )
    await client.post(
        f"{API}/sessions/{sid}/credentials",
        headers=headers,
        json={"name": "prom", "secret": {"endpoint": "https://prom.example"}},
    )
    with patch(
        "app.services.integration_onboarding.validate_prometheus",
        new_callable=AsyncMock,
        return_value={"ok": False, "status": "FAILED", "provider_mode": "unavailable", "errors": ["unreachable"]},
    ):
        await client.post(f"{API}/sessions/{sid}/validate", headers=headers)

    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        count = (await session.execute(
            select(func.count()).select_from(IntConnectionRegistry).where(
                IntConnectionRegistry.organization_id == org_id,
                IntConnectionRegistry.lifecycle_state == "CONNECTED",
            ),
        )).scalar_one()
        assert count == 0


@pytest.mark.asyncio
async def test_github_workflow_unavailable_insufficient_evidence(client):
    headers, _, _ = await _admin_client(client)
    sid = (await client.post(f"{API}/sessions", headers=headers, json={"provider_type": "GITHUB"})).json()["id"]
    await client.put(
        f"{API}/sessions/{sid}/environment",
        headers=headers,
        json={
            "environment_name": "staging",
            "environment_classification": "staging",
            "scope": {"repository": "org/repo"},
            "intended_for_pilot": True,
        },
    )
    await client.post(
        f"{API}/sessions/{sid}/credentials",
        headers=headers,
        json={"name": "gh", "secret": {"token": "ghp_testtoken1234567890"}},
    )
    with patch(
        "app.services.integration_onboarding.validate_source_control",
        new_callable=AsyncMock,
        return_value=GITHUB_OK,
    ):
        result = await client.post(f"{API}/sessions/{sid}/validate", headers=headers)
    assert result.status_code == 200
    assert result.json()["readiness_verdict"] == "INSUFFICIENT_EVIDENCE"


@pytest.mark.asyncio
async def test_github_repository_scope_enforced(client):
    headers, _, _ = await _admin_client(client)
    sid = (await client.post(f"{API}/sessions", headers=headers, json={"provider_type": "GITHUB"})).json()["id"]
    resp = await client.put(
        f"{API}/sessions/{sid}/environment",
        headers=headers,
        json={
            "environment_name": "staging",
            "environment_classification": "staging",
            "scope": {"repository": "*"},
            "intended_for_pilot": True,
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_rbac_report_and_least_privilege_guide(client):
    headers, _, _ = await _admin_client(client)
    sid = (await client.post(f"{API}/sessions", headers=headers, json={"provider_type": "KUBERNETES"})).json()["id"]
    await client.put(
        f"{API}/sessions/{sid}/environment",
        headers=headers,
        json={
            "environment_name": "staging",
            "environment_classification": "staging",
            "scope": {"namespace": "pilot-ns"},
            "intended_for_pilot": True,
        },
    )
    await client.post(
        f"{API}/sessions/{sid}/credentials",
        headers=headers,
        json={"name": "k8s", "secret": {"kubeconfig": "apiVersion: v1\n"}},
    )
    with patch("app.services.integration_onboarding.validate_kubernetes", new_callable=AsyncMock, return_value=K8S_OK):
        await client.post(f"{API}/sessions/{sid}/validate", headers=headers)

    rbac = await client.get(f"{API}/sessions/{sid}/rbac-report", headers=headers)
    assert rbac.status_code == 200
    guide = await client.get(f"{API}/sessions/{sid}/least-privilege-guide", headers=headers)
    assert guide.status_code == 200
    assert "deployments" in (guide.json().get("minimum_rbac_yaml") or "")


@pytest.mark.asyncio
async def test_credential_redaction_in_responses_and_audit(client):
    headers, org_id, user_id = await _admin_client(client)
    token = "ghp_supersecret_token_value_12345"
    sid = (await client.post(f"{API}/sessions", headers=headers, json={"provider_type": "GITHUB"})).json()["id"]
    await client.put(
        f"{API}/sessions/{sid}/environment",
        headers=headers,
        json={
            "environment_name": "staging",
            "environment_classification": "staging",
            "scope": {"repository": "org/repo"},
            "intended_for_pilot": True,
        },
    )
    resp = await client.post(
        f"{API}/sessions/{sid}/credentials",
        headers=headers,
        json={"name": "gh", "secret": {"token": token}},
    )
    body = json.dumps(resp.json())
    assert token not in body
    assert "credential_id" in resp.json()

    from app.database.session import AsyncSessionLocal
    from app.models.audit import AuditLog

    async with AsyncSessionLocal() as session:
        logs = list((await session.execute(
            select(AuditLog).where(AuditLog.organization_id == org_id),
        )).scalars().all())
        blob = json.dumps([l.details for l in logs if l.details])
        assert token not in blob

    evidence = await client.get(f"{API}/sessions/{sid}/evidence", headers=headers)
    assert token not in evidence.text


@pytest.mark.asyncio
async def test_onboarding_no_pilot_side_effects(client):
    headers, org_id, _ = await _admin_client(client)
    from app.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        before_e = (await session.execute(
            select(func.count()).select_from(PilotEnrollment).where(PilotEnrollment.organization_id == org_id),
        )).scalar_one()
        before_o = (await session.execute(
            select(func.count()).select_from(PilotLiveOperation).where(PilotLiveOperation.organization_id == org_id),
        )).scalar_one()
        before_a = (await session.execute(
            select(func.count()).select_from(PilotApproval).where(PilotApproval.organization_id == org_id),
        )).scalar_one()
        before_s = (await session.execute(
            select(func.count()).select_from(PilotStage).where(PilotStage.organization_id == org_id),
        )).scalar_one()

    sid = (await client.post(f"{API}/sessions", headers=headers, json={"provider_type": "KUBERNETES"})).json()["id"]
    await client.put(
        f"{API}/sessions/{sid}/environment",
        headers=headers,
        json={
            "environment_name": "staging",
            "environment_classification": "staging",
            "scope": {"namespace": "pilot-ns"},
            "intended_for_pilot": True,
        },
    )
    await client.post(
        f"{API}/sessions/{sid}/credentials",
        headers=headers,
        json={"name": "k8s", "secret": {"kubeconfig": "apiVersion: v1\n"}},
    )
    with patch("app.services.integration_onboarding.validate_kubernetes", new_callable=AsyncMock, return_value=K8S_OK):
        await client.post(f"{API}/sessions/{sid}/validate", headers=headers)
    await client.post(f"{API}/sessions/{sid}/acknowledge", headers=headers, json={"acknowledged": True})
    await client.get(f"{API}/readiness", headers=headers)

    async with AsyncSessionLocal() as session:
        after_e = (await session.execute(
            select(func.count()).select_from(PilotEnrollment).where(PilotEnrollment.organization_id == org_id),
        )).scalar_one()
        after_o = (await session.execute(
            select(func.count()).select_from(PilotLiveOperation).where(PilotLiveOperation.organization_id == org_id),
        )).scalar_one()
        after_a = (await session.execute(
            select(func.count()).select_from(PilotApproval).where(PilotApproval.organization_id == org_id),
        )).scalar_one()
        after_s = (await session.execute(
            select(func.count()).select_from(PilotStage).where(PilotStage.organization_id == org_id),
        )).scalar_one()

    assert before_e == after_e == 0
    assert before_o == after_o == 0
    assert before_a == after_a == 0
    assert before_s == after_s == 0


@pytest.mark.asyncio
async def test_tenant_isolation(client):
    h1, _, _ = await _admin_client(client)
    user2, tokens2 = await create_authenticated_user(
        client, email="onboard-iso@e.com", username="onboardiso", password="Pass123!",
    )
    org2 = await create_organization(client, tokens2["access_token"], name="Iso Org", slug="iso-org")
    switched2 = await switch_organization(client, tokens2["access_token"], org2["id"])
    h2 = auth_headers(switched2["access_token"])

    sid = (await client.post(f"{API}/sessions", headers=h1, json={"provider_type": "KUBERNETES"})).json()["id"]
    denied = await client.get(f"{API}/sessions/{sid}", headers=h2)
    assert denied.status_code == 404


@pytest.mark.asyncio
async def test_launch_readiness_integration(client):
    headers, _, _ = await _admin_client(client)
    resp = await client.get(f"{API}/readiness", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] in ("GO", "NO_GO", "INSUFFICIENT_EVIDENCE")
    assert body["read_only"] is True


@pytest.mark.asyncio
async def test_acknowledge_ready_for_pilot(client):
    headers, _, _ = await _admin_client(client)
    sid = (await client.post(f"{API}/sessions", headers=headers, json={"provider_type": "KUBERNETES"})).json()["id"]
    await client.put(
        f"{API}/sessions/{sid}/environment",
        headers=headers,
        json={
            "environment_name": "staging",
            "environment_classification": "staging",
            "scope": {"namespace": "pilot-ns"},
            "intended_for_pilot": True,
        },
    )
    await client.post(
        f"{API}/sessions/{sid}/credentials",
        headers=headers,
        json={"name": "k8s", "secret": {"kubeconfig": "apiVersion: v1\n"}},
    )
    with patch("app.services.integration_onboarding.validate_kubernetes", new_callable=AsyncMock, return_value=K8S_OK):
        await client.post(f"{API}/sessions/{sid}/validate", headers=headers)
    ack = await client.post(f"{API}/sessions/{sid}/acknowledge", headers=headers, json={"acknowledged": True})
    assert ack.status_code == 200
    assert ack.json()["status"] == "READY_FOR_PILOT"


def test_redact_text_removes_tokens():
    text = "Authorization: Bearer ghp_abc123secret"
    out = redact_text(text)
    assert "ghp_abc123secret" not in out
    assert "REDACTED" in out


@pytest.mark.asyncio
async def test_prometheus_safe_query_validation(client):
    headers, _, _ = await _admin_client(client)
    sid = (await client.post(f"{API}/sessions", headers=headers, json={"provider_type": "PROMETHEUS"})).json()["id"]
    await client.put(
        f"{API}/sessions/{sid}/environment",
        headers=headers,
        json={
            "environment_name": "staging",
            "environment_classification": "staging",
            "scope": {"namespace_label": "namespace", "namespace_label_value": "pilot-ns"},
            "intended_for_pilot": True,
        },
    )
    await client.post(
        f"{API}/sessions/{sid}/credentials",
        headers=headers,
        json={"name": "prom", "secret": {"endpoint": "https://prom.example"}},
    )
    with patch(
        "app.services.integration_onboarding.validate_prometheus",
        new_callable=AsyncMock,
        return_value=PROM_OK,
    ):
        result = await client.post(f"{API}/sessions/{sid}/validate", headers=headers)
    assert result.status_code == 200
    assert result.json()["status"] == "VALIDATED"


@pytest.mark.asyncio
async def test_validate_source_control_uses_http_request_status_key():
    from app.integration_onboarding.validators import validate_source_control
    from app.services.integration_verification import VStatus, VerificationResult

    mock_result = VerificationResult(
        connection_status=VStatus.CONNECTED,
        latency_ms=1,
        provider_version=None,
        verified_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        provider_identity={"login": "pilot-admin"},
        permissions=["read"],
        warnings=[],
        errors=[],
        confidence=90,
    )

    async def fake_http_request(method, url, *, headers=None, params=None, json_body=None, auth=None):
        if "/repos/" in url and "/actions/" not in url:
            return {"_status": 200, "_headers": {}, "_json": {"full_name": "pilot-admin/pilot-test"}}
        return {"_status": 404, "_headers": {}, "_json": {}}

    with patch(
        "app.integration_onboarding.validators.verify_provider",
        new_callable=AsyncMock,
        return_value=mock_result,
    ), patch(
        "app.services.integration_verification._http_request",
        new=fake_http_request,
    ):
        out = await validate_source_control(
            "GITEA",
            {"token": "t", "base_url": "http://pilot-gitea:3000/api/v1"},
            repository="pilot-admin/pilot-test",
            api_base_url="http://pilot-gitea:3000/api/v1",
        )

    assert out["ok"] is True
    assert out["capabilities"]["repository_access"] is True
