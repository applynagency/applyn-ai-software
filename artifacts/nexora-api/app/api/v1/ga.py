"""GA readiness API (Sprint 64A).

* ``/v1/ga/install``           — first-run setup + readiness report
* ``/v1/ga/upgrade``            — pre/post upgrade validation + migration preview
* ``/v1/ga/backups``            — backup catalog, verify, restore
* ``/v1/ga/health``             — operational health center
* ``/v1/ga/diagnostics``        — diagnostics bundle (JSON + ZIP)
* ``/v1/ga/support``            — support tokens + reproduction package
* ``/v1/ga/release``            — release channels + staged rollouts
* ``/v1/ga/compliance``         — compliance evidence reports
* ``/v1/ga/marketplace``        — plugin marketplace
* ``/v1/ga/success``              — customer success / adoption
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from app.auth.dependencies import DBSession
from app.auth.org_context import OrgContext, OrgContextDep
from app.core.config import settings
from app.models.organization import OrganizationRole
from app.platform.ga import (
    BackupManagerService,
    ComplianceCenterService,
    CustomerSuccessService,
    DiagnosticsBundleService,
    HealthCenterService,
    InstallationService,
    MarketplaceService,
    ReleaseManagementService,
    SupportModeService,
    UpgradeService,
)
from app.schemas.ga import (
    BackupCreateRequest,
    BackupResponse,
    ComplianceReportRequest,
    ComplianceReportResponse,
    CustomerSuccessResponse,
    InstallRunRequest,
    InstallRunResponse,
    ReleaseChannelRequest,
    SupportTokenRequest,
)

router = APIRouter(prefix="/ga", tags=["GA Readiness"])

_ADMIN_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN}


def _org(ctx: OrgContext) -> str:
    return ctx.requires_organization


# --------------------------------------------------------------------------- #
# Installation
# --------------------------------------------------------------------------- #
@router.post("/install/readiness", response_model=InstallRunResponse,
             status_code=status.HTTP_201_CREATED)
async def run_install_readiness(body: InstallRunRequest, session: DBSession,
                                ctx: OrgContextDep):
    org_id = _org(ctx)
    run = await InstallationService(session).run_readiness(
        organization_id=org_id, load_sample_data=body.load_sample_data,
        bootstrap_admin=body.bootstrap_admin, user_id=ctx.user.id)
    await session.commit()
    return run


# --------------------------------------------------------------------------- #
# Upgrade
# --------------------------------------------------------------------------- #
@router.get("/upgrade/pre-check")
async def upgrade_pre_check(session: DBSession, ctx: OrgContextDep):
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(status_code=403, detail="Admin required")
    return await UpgradeService(session).pre_upgrade_validation()


@router.get("/upgrade/migration-preview")
async def migration_preview(session: DBSession, ctx: OrgContextDep):
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(status_code=403, detail="Admin required")
    return await UpgradeService(session).migration_preview()


@router.get("/upgrade/post-verify")
async def upgrade_post_verify(session: DBSession, ctx: OrgContextDep):
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(status_code=403, detail="Admin required")
    return await UpgradeService(session).post_upgrade_verification()


# --------------------------------------------------------------------------- #
# Backups
# --------------------------------------------------------------------------- #
@router.get("/backups", response_model=list[BackupResponse])
async def list_backups(session: DBSession, ctx: OrgContextDep):
    org_id = _org(ctx)
    return await BackupManagerService(session).list_catalog(organization_id=org_id)


@router.post("/backups", response_model=BackupResponse, status_code=status.HTTP_201_CREATED)
async def create_backup(body: BackupCreateRequest, session: DBSession, ctx: OrgContextDep):
    org_id = _org(ctx)
    record = await BackupManagerService(session).create_backup(
        organization_id=org_id, label=body.label,
        schedule_cadence=body.schedule_cadence, retention_days=body.retention_days,
        user_id=ctx.user.id)
    await session.commit()
    return record


@router.post("/backups/{backup_id}/verify", response_model=BackupResponse)
async def verify_backup(backup_id: str, session: DBSession, ctx: OrgContextDep):
    record = await BackupManagerService(session).verify_backup(backup_id)
    if record is None:
        raise HTTPException(status_code=404, detail="backup not found")
    await session.commit()
    return record


@router.post("/backups/{backup_id}/restore")
async def restore_backup(backup_id: str, session: DBSession, ctx: OrgContextDep):
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(status_code=403, detail="Admin required")
    try:
        hist = await BackupManagerService(session).restore(
            backup_id, organization_id=_org(ctx), user_id=ctx.user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    await session.commit()
    return {"restore_id": hist.id, "status": hist.status, "result": hist.result}


# --------------------------------------------------------------------------- #
# Health center
# --------------------------------------------------------------------------- #
@router.get("/health")
async def health_center(session: DBSession, ctx: OrgContextDep):
    return await HealthCenterService(session).dashboard(organization_id=_org(ctx))


# --------------------------------------------------------------------------- #
# Diagnostics
# --------------------------------------------------------------------------- #
@router.get("/diagnostics")
async def diagnostics_json(session: DBSession, ctx: OrgContextDep):
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(status_code=403, detail="Admin required")
    return await DiagnosticsBundleService(session).collect(organization_id=_org(ctx))


@router.get("/diagnostics/zip")
async def diagnostics_zip(session: DBSession, ctx: OrgContextDep):
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(status_code=403, detail="Admin required")
    data = await DiagnosticsBundleService(session).export_zip(organization_id=_org(ctx))
    return Response(
        content=data, media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=nexora-diagnostics.zip"},
    )


# --------------------------------------------------------------------------- #
# Support mode
# --------------------------------------------------------------------------- #
@router.post("/support/token")
async def issue_support_token(body: SupportTokenRequest, session: DBSession,
                              ctx: OrgContextDep):
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(status_code=403, detail="Admin required")
    result = await SupportModeService(session).issue_token(
        organization_id=_org(ctx), created_by=ctx.user.id,
        ttl_hours=body.ttl_hours, read_only=body.read_only)
    await session.commit()
    return result


@router.get("/support/reproduction-package")
async def reproduction_package(session: DBSession, ctx: OrgContextDep):
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(status_code=403, detail="Admin required")
    return await SupportModeService(session).reproduction_package(
        organization_id=_org(ctx))


# --------------------------------------------------------------------------- #
# Release management
# --------------------------------------------------------------------------- #
@router.get("/release/channel")
async def get_release_channel(session: DBSession, ctx: OrgContextDep):
    channel = await ReleaseManagementService(session).get_channel(_org(ctx))
    compat = ReleaseManagementService(session).version_compatible(settings.APP_VERSION)
    return {"channel": channel, "version": compat}


@router.put("/release/channel")
async def set_release_channel(body: ReleaseChannelRequest, session: DBSession,
                              ctx: OrgContextDep):
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(status_code=403, detail="Admin required")
    try:
        result = await ReleaseManagementService(session).set_channel(
            _org(ctx), body.channel, updated_by=ctx.user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    await session.commit()
    return result


@router.post("/release/rollout/{feature}")
async def staged_rollout(feature: str, session: DBSession, ctx: OrgContextDep,
                         percent: int = Query(0, ge=0, le=100)):
    if not ctx.user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser required")
    result = await ReleaseManagementService(session).staged_rollout(
        feature, percent, updated_by=ctx.user.id)
    await session.commit()
    return result


# --------------------------------------------------------------------------- #
# Compliance
# --------------------------------------------------------------------------- #
@router.post("/compliance/reports", response_model=ComplianceReportResponse,
             status_code=status.HTTP_201_CREATED)
async def generate_compliance_report(body: ComplianceReportRequest, session: DBSession,
                                     ctx: OrgContextDep):
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(status_code=403, detail="Admin required")
    try:
        report = await ComplianceCenterService(session).generate_report(
            organization_id=_org(ctx), framework=body.framework, user_id=ctx.user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    await session.commit()
    return report


# --------------------------------------------------------------------------- #
# Marketplace
# --------------------------------------------------------------------------- #
@router.get("/marketplace")
async def marketplace_discover(session: DBSession, ctx: OrgContextDep):
    return await MarketplaceService(session).discover()


@router.post("/marketplace/{slug}/install")
async def marketplace_install(slug: str, session: DBSession, ctx: OrgContextDep):
    result = await MarketplaceService(session).install(
        _org(ctx), slug, user_id=ctx.user.id)
    await session.commit()
    return result


@router.post("/marketplace/{slug}/upgrade")
async def marketplace_upgrade(slug: str, session: DBSession, ctx: OrgContextDep):
    result = await MarketplaceService(session).upgrade(_org(ctx), slug)
    await session.commit()
    return result


# --------------------------------------------------------------------------- #
# Customer success
# --------------------------------------------------------------------------- #
@router.get("/success", response_model=CustomerSuccessResponse)
async def customer_success(session: DBSession, ctx: OrgContextDep):
    row = await CustomerSuccessService(session).refresh(organization_id=_org(ctx))
    await session.commit()
    return row
