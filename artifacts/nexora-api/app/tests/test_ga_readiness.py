"""Sprint 64A — GA Readiness tests."""

from __future__ import annotations

import pytest

from app.database.session import AsyncSessionLocal
from app.models.incident import IncidentInvestigation, IncidentInvestigationStatus
from app.models.organization import Organization
from app.platform.ga import (
    BackupManagerService,
    ComplianceCenterService,
    CustomerSuccessService,
    DiagnosticsBundleService,
    HealthCenterService,
    InstallationService,
    ReleaseManagementService,
    SupportModeService,
    UpgradeService,
)

from .conftest import (
    auth_headers,
    create_authenticated_user,
    create_organization,
    switch_organization,
)


async def _make_org(session, name="GA Co") -> str:
    org = Organization(name=name, slug=name.lower().replace(" ", "-"))
    session.add(org)
    await session.flush()
    return org.id


async def _make_incident(session, org_id: str) -> str:
    inv = IncidentInvestigation(
        organization_id=org_id, title="Test incident", prompt="test",
        status=IncidentInvestigationStatus.COMPLETED.value,
        summary="summary", root_cause="test cause",
    )
    session.add(inv)
    await session.flush()
    return inv.id


@pytest.mark.asyncio
async def test_installation_readiness(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        run = await InstallationService(session).run_readiness(organization_id=org_id)
        await session.commit()
        assert run.readiness_score >= 0
        assert run.readiness_report
        assert len(run.checks or []) >= 7


@pytest.mark.asyncio
async def test_upgrade_framework(setup_db):
    async with AsyncSessionLocal() as session:
        pre = await UpgradeService(session).pre_upgrade_validation()
        preview = await UpgradeService(session).migration_preview()
        post = await UpgradeService(session).post_upgrade_verification()
        assert "migration" in pre
        assert "head_revision" in preview
        assert "verified_at" in post


@pytest.mark.asyncio
async def test_backup_manager(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        svc = BackupManagerService(session)
        backup = await svc.create_backup(organization_id=org_id, label="test")
        verified = await svc.verify_backup(backup.id)
        hist = await svc.restore(backup.id, organization_id=org_id)
        await session.commit()
        assert verified is not None
        assert verified.status == "VERIFIED"
        assert hist.status == "COMPLETED"


@pytest.mark.asyncio
async def test_health_center(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        dash = await HealthCenterService(session).dashboard(organization_id=org_id)
        assert "health_score" in dash
        assert "components" in dash


@pytest.mark.asyncio
async def test_diagnostics_zip(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        data = await DiagnosticsBundleService(session).export_zip(organization_id=org_id)
        assert data[:2] == b"PK"


@pytest.mark.asyncio
async def test_support_token(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        issued = await SupportModeService(session).issue_token(
            organization_id=org_id, created_by="user-1", ttl_hours=1)
        validated = await SupportModeService(session).validate_token(issued["token"])
        await session.commit()
        assert validated is not None


@pytest.mark.asyncio
async def test_compliance_evidence_only(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        report = await ComplianceCenterService(session).generate_report(
            organization_id=org_id, framework="SOC2")
        await session.commit()
        assert report.evidence
        assert report.readiness_score >= 0


@pytest.mark.asyncio
async def test_customer_success(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        await _make_incident(session, org_id)
        row = await CustomerSuccessService(session).refresh(organization_id=org_id)
        await session.commit()
        assert row.milestones
        assert row.adoption_score >= 0


@pytest.mark.asyncio
async def test_release_channel(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session)
        svc = ReleaseManagementService(session)
        await svc.set_channel(org_id, "preview")
        await session.commit()
        assert await svc.get_channel(org_id) == "preview"
        compat = svc.version_compatible("1.0.0")
        assert compat["compatible"] is True


@pytest.mark.asyncio
async def test_ga_api_smoke(client):
    from app.core.security import decode_token

    me, tokens = await create_authenticated_user(
        client, email="ga@example.com", username="gauser")
    claims = decode_token(tokens["access_token"])
    if not claims.get("organization_id"):
        org = await create_organization(client, tokens["access_token"], name="GA Org")
        await switch_organization(client, tokens["access_token"], org["id"])
        from .conftest import login_user
        tokens = await login_user(client, email="ga@example.com")
    h = auth_headers(tokens["access_token"])

    readiness = await client.post("/v1/ga/install/readiness", headers=h, json={})
    assert readiness.status_code == 201, readiness.text

    health = await client.get("/v1/ga/health", headers=h)
    assert health.status_code == 200
    assert "health_score" in health.json()

    backup = await client.post("/v1/ga/backups", headers=h, json={"label": "api-test"})
    assert backup.status_code == 201

    success = await client.get("/v1/ga/success", headers=h)
    assert success.status_code == 200

    marketplace = await client.get("/v1/ga/marketplace", headers=h)
    assert marketplace.status_code == 200

    compliance = await client.post("/v1/ga/compliance/reports", headers=h,
                                   json={"framework": "GDPR"})
    assert compliance.status_code == 201

    channel = await client.get("/v1/ga/release/channel", headers=h)
    assert channel.status_code == 200

    diag = await client.get("/v1/ga/diagnostics", headers=h)
    assert diag.status_code == 200

    token = await client.post("/v1/ga/support/token", headers=h, json={"ttl_hours": 1})
    assert token.status_code == 200

    zip_resp = await client.get("/v1/ga/diagnostics/zip", headers=h)
    assert zip_resp.status_code == 200
    assert zip_resp.headers.get("content-type", "").startswith("application/zip")
