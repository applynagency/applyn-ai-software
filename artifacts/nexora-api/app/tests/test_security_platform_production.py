"""Sprint 65E — Security Platform production integration tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.security_platform.backfill import import_fingerprint
from app.security_platform.executor import detect_mode, redact_output, validate_argv
from app.security_platform.gates import evaluate_gate
from app.security_platform.providers.execution import validate_provider
from app.security_platform.remediation_exec import requires_human_approval
from app.security_platform.sbom_parser import normalize_component_key, parse_sbom
from app.security_platform.sla import evaluate_sla, sla_dashboard_counts
from app.tests.conftest import auth_headers, create_authenticated_user

CYCLONEDX_SAMPLE = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.4",
    "components": [
        {"type": "library", "name": "lodash", "version": "4.17.20", "purl": "pkg:npm/lodash@4.17.20",
         "licenses": [{"license": {"id": "MIT"}}]},
        {"type": "library", "name": "express", "version": "4.18.0", "purl": "pkg:npm/express@4.18.0"},
    ],
    "dependencies": [{"ref": "pkg:npm/express@4.18.0", "dependsOn": ["pkg:npm/lodash@4.17.20"]}],
}

SPDX_SAMPLE = {
    "spdxVersion": "SPDX-2.3",
    "packages": [
        {"name": "requests", "versionInfo": "2.28.0", "licenseConcluded": "Apache-2.0",
         "externalRefs": [{"referenceType": "purl", "referenceLocator": "pkg:pypi/requests@2.28.0"}]},
    ],
}


def test_redact_output_strips_secrets():
    out = redact_output("api_key=sk-live-secret-value")
    assert "sk-live" not in out
    assert "[REDACTED]" in out


def test_validate_argv_rejects_unknown():
    with pytest.raises(ValueError, match="not allowlisted"):
        validate_argv("trivy", ["trivy", "image", "/etc/passwd"])


def test_cyclonedx_parsing():
    parsed = parse_sbom(CYCLONEDX_SAMPLE)
    assert parsed["format"] == "cyclonedx"
    assert parsed["component_count"] == 2
    assert parsed["components"][0]["name"] == "lodash"


def test_spdx_parsing():
    parsed = parse_sbom(SPDX_SAMPLE)
    assert parsed["format"] == "spdx"
    assert parsed["components"][0]["name"] == "requests"


def test_component_normalization_dedup():
    k1 = normalize_component_key(name="Lodash", version="1.0", ecosystem="npm")
    k2 = normalize_component_key(name="lodash", version="1.0", ecosystem="npm")
    assert k1 == k2


def test_import_fingerprint_idempotent():
    fp1 = import_fingerprint(org_id="o1", source_system="cp", source_record_id="r1")
    fp2 = import_fingerprint(org_id="o1", source_system="cp", source_record_id="r1")
    assert fp1 == fp2


def test_provider_mode_offline_without_binary(monkeypatch):
    monkeypatch.setattr("app.security_platform.executor.shutil.which", lambda _: None)
    assert detect_mode("TRIVY", enabled=True) == "offline"
    assert detect_mode("TRIVY", enabled=False) == "unavailable"


@pytest.mark.asyncio
async def test_validate_provider_offline(monkeypatch):
    monkeypatch.setattr("app.security_platform.executor.shutil.which", lambda _: None)
    result = await validate_provider("TRIVY", enabled=True)
    assert result["mode"] == "offline"


def test_gate_block_on_critical():
    gate = evaluate_gate(
        [{"severity": "CRITICAL", "status": "OPEN", "title": "RCE", "id": "f1"}],
        policy_mode="BLOCK",
    )
    assert gate["decision"] == "BLOCK"
    assert gate["blocked"] is True
    assert "api_key" not in json.dumps(gate)


def test_remediation_approval_enforcement():
    assert requires_human_approval("REVOKE_API_KEY") is True
    assert requires_human_approval("CREATE_TICKET", org_policy={"auto_execute_low_risk": True}) is False


def test_sla_breach_detection():
    past = datetime.now(UTC) - timedelta(days=2)
    ev = evaluate_sla(
        {"severity": "CRITICAL", "status": "OPEN", "created_at": past, "sla_due_at": past + timedelta(days=1)},
        policies=[{"severity": "CRITICAL", "due_days": 1, "enabled": True}],
    )
    assert ev["sla_breached"] is True


def test_sla_dashboard_counts():
    counts = sla_dashboard_counts([
        {"severity": "HIGH", "status": "OPEN", "created_at": datetime.now(UTC)},
        {"severity": "LOW", "status": "ACCEPTED_RISK", "created_at": datetime.now(UTC)},
    ], policies=[{"severity": "HIGH", "due_days": 7, "warning_hours": 24, "enabled": True}])
    assert counts["accepted_risk"] == 1


@pytest.mark.asyncio
async def test_backfill_dry_run_idempotent(client):
    _, tokens = await create_authenticated_user(client, email="bf1@e.com", username="bfuser1")
    headers = auth_headers(tokens["access_token"])
    r1 = await client.post("/v1/security/backfill/dry-run", headers=headers)
    assert r1.status_code == 200
    r2 = await client.post("/v1/security/backfill/dry-run", headers=headers)
    assert r2.status_code == 200
    assert "counts" in r1.json()


@pytest.mark.asyncio
async def test_provider_config_and_validate(client):
    _, tokens = await create_authenticated_user(client, email="pv1@e.com", username="pvuser1")
    headers = auth_headers(tokens["access_token"])
    created = await client.post(
        "/v1/security/providers",
        headers=headers,
        json={"provider_type": "TRIVY", "name": "Trivy", "enabled": False},
    )
    assert created.status_code == 201
    assert created.json()["mode"] in ("offline", "unavailable", "live")
    validated = await client.post(
        f"/v1/security/providers/{created.json()['id']}/validate", headers=headers,
    )
    assert validated.status_code == 200


@pytest.mark.asyncio
async def test_sbom_import_and_components(client):
    _, tokens = await create_authenticated_user(client, email="sb1@e.com", username="sbuser1")
    headers = auth_headers(tokens["access_token"])
    imp = await client.post(
        "/v1/security/sbom/import",
        headers=headers,
        json={"format": "cyclonedx", "target": "api:latest", "content": CYCLONEDX_SAMPLE},
    )
    assert imp.status_code == 200
    assert imp.json()["components_imported"] == 2
    comps = await client.get("/v1/security/sbom/components", headers=headers)
    assert comps.status_code == 200
    assert comps.json()["total"] >= 2


@pytest.mark.asyncio
async def test_scan_runs_and_sla(client):
    _, tokens = await create_authenticated_user(client, email="sr1@e.com", username="sruser1")
    headers = auth_headers(tokens["access_token"])
    await client.post(
        "/v1/security/scans", headers=headers,
        json={"kind": "SECRET", "target": "repo/checkout"},
    )
    runs = await client.get("/v1/security/scan-runs", headers=headers)
    assert runs.status_code == 200
    assert runs.json()["total"] >= 1
    sla = await client.get("/v1/security/sla", headers=headers)
    assert sla.status_code == 200
    assert "dashboard" in sla.json()


@pytest.mark.asyncio
async def test_remediation_execution_flow(client):
    _, tokens = await create_authenticated_user(client, email="re1@e.com", username="reuser1")
    headers = auth_headers(tokens["access_token"])
    await client.post(
        "/v1/security/scans", headers=headers,
        json={"kind": "DEPENDENCY", "target": "package-lock.json"},
    )
    findings = await client.get("/v1/security/findings", headers=headers)
    items = findings.json().get("items", [])
    if not items:
        pytest.skip("no findings")
    fid = items[0]["id"]
    prop = await client.post(
        "/v1/security/remediation", headers=headers,
        json={"finding_id": fid, "kind": "CREATE_TICKET", "title": "Track fix"},
    )
    pid = prop.json()["id"]
    await client.post(f"/v1/security/remediation/{pid}/decide?approved=true", headers=headers)
    exe = await client.post(f"/v1/security/remediation/{pid}/execute", headers=headers)
    assert exe.status_code == 200
    detail = await client.get(f"/v1/security/remediation/{pid}/execution", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["checkpoints"]


@pytest.mark.asyncio
async def test_tenant_isolation_providers(client):
    _, tokens1 = await create_authenticated_user(client, email="ti1@e.com", username="tiuser1")
    _, tokens2 = await create_authenticated_user(client, email="ti2@e.com", username="tiuser2")
    h1 = auth_headers(tokens1["access_token"])
    h2 = auth_headers(tokens2["access_token"])
    created = await client.post(
        "/v1/security/providers", headers=h1,
        json={"provider_type": "GITLEAKS", "name": "Gitleaks", "enabled": False},
    )
    pid = created.json()["id"]
    other = await client.post(f"/v1/security/providers/{pid}/validate", headers=h2)
    assert other.status_code in (403, 404)


def test_migration_0031_revision_chain():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0031_security_production.py"
    spec = importlib.util.spec_from_file_location("migration_0031", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.down_revision == "0030_security_platform"
    assert m.revision == "0031_security_production"
