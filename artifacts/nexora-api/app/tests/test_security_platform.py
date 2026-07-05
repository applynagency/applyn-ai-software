"""Enterprise DevSecOps Security Platform tests (Sprint 65D)."""

from __future__ import annotations

import pytest

from app.security_platform.analytics import compute_posture
from app.security_platform.findings import fingerprint, normalize_finding, transition_status
from app.security_platform.providers import registry as sec_registry
from app.services.security_platform import _redact_evidence
from app.tests.conftest import auth_headers, create_authenticated_user


def test_fingerprint_dedup():
    fp1 = fingerprint(source="DEPENDENCY", title="CVE-1", resource="pkg/a", cve="CVE-1", org_id="org1")
    fp2 = fingerprint(source="DEPENDENCY", title="CVE-1", resource="pkg/a", cve="CVE-1", org_id="org1")
    fp3 = fingerprint(source="DEPENDENCY", title="CVE-2", resource="pkg/a", cve="CVE-2", org_id="org1")
    assert fp1 == fp2
    assert fp1 != fp3


def test_lifecycle_transition():
    status, hist = transition_status("OPEN", "ACKNOWLEDGED", actor="user1")
    assert status == "ACKNOWLEDGED"
    assert hist["actor"] == "user1"
    with pytest.raises(ValueError):
        transition_status("RESOLVED", "ACKNOWLEDGED")


def test_secret_redaction():
    data = {"api_key": "sk-live-abc", "title": "finding"}
    redacted = _redact_evidence(data)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["title"] == "finding"


def test_offline_scan_adapter():
    result = sec_registry.run_scan("SECRET", "repo/checkout")
    assert result.get("simulated") is True
    assert result.get("findings")


def test_posture_scoring():
    data = compute_posture(findings=[
        {"severity": "CRITICAL", "status": "OPEN"},
        {"severity": "HIGH", "status": "OPEN"},
    ])
    assert data["open_critical"] == 1
    assert data["posture_score"] < 100


@pytest.mark.asyncio
async def test_security_overview_and_providers(client):
    _, tokens = await create_authenticated_user(client, email="sec1@e.com", username="secuser1")
    token = tokens["access_token"]
    headers = auth_headers(token)
    prov = await client.get("/v1/security/providers", headers=headers)
    assert prov.status_code == 200
    assert "scan_kinds" in prov.json()
    overview = await client.get("/v1/security/overview", headers=headers)
    assert overview.status_code == 200
    body = overview.json()
    assert "posture_score" in body
    assert body.get("live_data") is False
    assert body.get("data_sufficient") is False
    assert body.get("posture_score") is None


@pytest.mark.asyncio
async def test_security_scan_and_findings(client):
    _, tokens = await create_authenticated_user(client, email="sec2@e.com", username="secuser2")
    token = tokens["access_token"]
    headers = auth_headers(token)
    scan = await client.post(
        "/v1/security/scans",
        headers=headers,
        json={"kind": "CONTAINER", "target": "ghcr.io/org/api:latest", "enforce_gate": True},
    )
    assert scan.status_code == 201
    assert scan.json().get("simulated") is True
    findings = await client.get("/v1/security/findings", headers=headers)
    assert findings.status_code == 200
    assert "items" in findings.json()


@pytest.mark.asyncio
async def test_security_remediation_approval(client):
    _, tokens = await create_authenticated_user(client, email="sec3@e.com", username="secuser3")
    token = tokens["access_token"]
    headers = auth_headers(token)
    await client.post(
        "/v1/security/scans", headers=headers,
        json={"kind": "DEPENDENCY", "target": "package-lock.json"},
    )
    findings = await client.get("/v1/security/findings", headers=headers)
    items = findings.json().get("items", [])
    if not items:
        pytest.skip("no findings ingested")
    fid = items[0]["id"]
    prop = await client.post(
        "/v1/security/remediation", headers=headers,
        json={"finding_id": fid, "kind": "UPGRADE_DEPENDENCY", "title": "Bump dependency"},
    )
    assert prop.status_code == 201
    assert prop.json().get("requires_approval") is True
    decide = await client.post(f"/v1/security/remediation/{prop.json()['id']}/decide?approved=true", headers=headers)
    assert decide.status_code == 200


@pytest.mark.asyncio
async def test_security_investigation_and_analytics(client):
    _, tokens = await create_authenticated_user(client, email="sec4@e.com", username="secuser4")
    token = tokens["access_token"]
    headers = auth_headers(token)
    inv = await client.post("/v1/security/investigations", headers=headers, json={"title": "Investigate"})
    assert inv.status_code == 201
    analytics = await client.get("/v1/security/analytics", headers=headers)
    assert analytics.status_code == 200
    cloud = await client.get("/v1/security/cloud", headers=headers)
    assert cloud.status_code == 200
