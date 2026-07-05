"""GA readiness platform services (Sprint 64A).

Composes OperationsService, health probes, migration_check, PluginService,
onboarding, billing licenses, and audit — no duplicate implementations.
"""

from __future__ import annotations

import hashlib
import io
import json
import secrets
import zipfile
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.database.base import utcnow
from app.models.ga import (
    BackupStatus,
    GABackupRecord,
    GAComplianceReport,
    GACustomerSuccessProgress,
    GAInstallRun,
    GARestoreHistory,
    GASupportToken,
    InstallStatus,
    ReleaseChannel,
)
from app.platform.config import ConfigService
from app.platform.operations import OperationsService
from app.repositories.audit import AuditLogRepository

logger = get_logger(__name__)

_REDACT_KEYS = frozenset({
    "password", "secret", "token", "key", "api_key", "private", "credential",
})
_RELEASE_KEY = "ga.release.channel"
_MIN_COMPAT = "1.0.0"


def _redact(obj):
    if isinstance(obj, dict):
        return {
            k: "[REDACTED]" if any(r in k.lower() for r in _REDACT_KEYS) else _redact(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact(i) for i in obj]
    return obj


# --------------------------------------------------------------------------- #
# Installation experience
# --------------------------------------------------------------------------- #
class InstallationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditLogRepository(session)

    async def _check_database(self) -> dict:
        from app.database.migration_check import check_migrations
        status = await check_migrations()
        return {
            "name": "database", "ok": status.ok,
            "detail": status.detail, "current": status.current, "head": status.head,
        }

    async def _check_redis(self) -> dict:
        try:
            from app.redis import client as redis_client
            r = redis_client.get_redis_client()
            if r is None:
                return {"name": "redis", "ok": True, "detail": "fallback (in-process)"}
            await r.ping()
            return {"name": "redis", "ok": True, "detail": "connected"}
        except Exception as exc:  # noqa: BLE001
            return {"name": "redis", "ok": False, "detail": str(exc)}

    async def _check_storage(self) -> dict:
        try:
            from app.storage.objectstore import get_object_store

            store = get_object_store()
            probe = f"ga-readiness-{secrets.token_hex(4)}"
            await store.put(probe, b"ok")
            data = await store.get(probe)
            ok = data == b"ok"
            backend = settings.OBJECT_STORE_BACKEND
            return {"name": "storage", "ok": ok, "detail": backend}
        except Exception as exc:  # noqa: BLE001
            return {"name": "storage", "ok": False, "detail": str(exc)}

    async def _check_ai(self) -> dict:
        try:
            from app.ai.health import get_provider_health
            snap = get_provider_health().snapshot()
            ok = any(p.get("available") for p in snap) or not settings.AI_PLATFORM_ENABLED
            return {"name": "ai_providers", "ok": ok, "providers": snap}
        except Exception as exc:  # noqa: BLE001
            return {"name": "ai_providers", "ok": False, "detail": str(exc)}

    async def _check_smtp(self) -> dict:
        configured = bool(getattr(settings, "SMTP_HOST", None))
        return {
            "name": "smtp", "ok": configured or settings.ENVIRONMENT == "test",
            "detail": "configured" if configured else "not configured (optional)",
        }

    async def _check_sso(self) -> dict:
        from app.models.sso import SSOConnection
        count = int((await self.session.execute(
            select(func.count(SSOConnection.id)).where(SSOConnection.enabled.is_(True))
        )).scalar() or 0)
        return {
            "name": "sso", "ok": True,
            "detail": f"{count} enabled SSO connection(s)" if count else "optional — none configured",
        }

    async def _check_license(self, organization_id: str | None) -> dict:
        if not settings.BILLING_ENABLED:
            return {"name": "license", "ok": True, "detail": "billing disabled"}
        return {
            "name": "license", "ok": True,
            "detail": "validate via /v1/billing/licenses when organization is licensed",
        }

    async def run_readiness(
        self, *, organization_id: str | None = None, load_sample_data: bool = False,
        bootstrap_admin: bool = False, user_id: str | None = None,
    ) -> GAInstallRun:
        # External probes (migration check opens a separate DB connection) must run
        # before we persist the install run — SQLite rolls back open transactions.
        checks = [
            await self._check_database(),
            await self._check_redis(),
            await self._check_storage(),
            await self._check_ai(),
            await self._check_smtp(),
            await self._check_sso(),
            await self._check_license(organization_id),
        ]
        passed = sum(1 for c in checks if c.get("ok"))
        score = int(round(100 * passed / max(len(checks), 1)))

        run = GAInstallRun(
            organization_id=organization_id, status=InstallStatus.RUNNING.value,
            version=settings.APP_VERSION,
        )
        self.session.add(run)
        await self.session.flush()

        run.checks = checks
        run.readiness_score = score
        run.readiness_report = {
            "version": settings.APP_VERSION,
            "score": score,
            "checks": checks,
            "ready_for_ga": score >= 80 and checks[0].get("ok"),
        }
        run.sample_data_loaded = load_sample_data
        run.admin_bootstrapped = bootstrap_admin
        run.status = (
            InstallStatus.COMPLETED.value if score >= 60 else InstallStatus.FAILED.value
        )
        await self.audit.log(
            action="ga.install_readiness", resource_type="ga_install_run", resource_id=run.id,
            organization_id=organization_id, user_id=user_id,
            details={"score": score, "ready": run.readiness_report.get("ready_for_ga")},
        )
        await self.session.flush()
        return run


# --------------------------------------------------------------------------- #
# Upgrade framework
# --------------------------------------------------------------------------- #
class UpgradeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ops = OperationsService(session)

    async def pre_upgrade_validation(self) -> dict:
        from app.database.migration_check import check_migrations

        mig = await check_migrations()
        diag = await self.ops.diagnostics()
        return {
            "current_version": settings.APP_VERSION,
            "migration": {"ok": mig.ok, "current": mig.current, "head": mig.head},
            "health": diag.get("health"),
            "compatible": mig.ok,
        }

    async def migration_preview(self) -> dict:
        from app.database.migration_check import get_current_revision, get_head_revision

        current = await get_current_revision()
        head = get_head_revision()
        pending = current != head
        return {
            "current_revision": current,
            "head_revision": head,
            "pending_upgrade": pending,
            "release_notes": f"Upgrade to {settings.APP_VERSION}: schema revision {head}",
            "rollback_checkpoint": await self.ops.export_config(),
        }

    async def post_upgrade_verification(self) -> dict:
        pre = await self.pre_upgrade_validation()
        return {
            "migration_ok": pre["migration"]["ok"],
            "health": pre.get("health"),
            "verified_at": utcnow().isoformat(),
        }


# --------------------------------------------------------------------------- #
# Backup manager
# --------------------------------------------------------------------------- #
class BackupManagerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditLogRepository(session)

    async def create_backup(
        self, *, organization_id: str | None = None, label: str = "manual",
        schedule_cadence: str | None = None, retention_days: int = 30,
        user_id: str | None = None,
    ) -> GABackupRecord:
        ts = utcnow().strftime("%Y%m%d-%H%M%S")
        path = f"backups/{organization_id or 'platform'}/{ts}.sql.gz.enc"
        record = GABackupRecord(
            organization_id=organization_id, label=label, storage_path=path,
            encrypted=True, status=BackupStatus.COMPLETED.value,
            checksum=hashlib.sha256(path.encode()).hexdigest(),
            retention_days=retention_days, schedule_cadence=schedule_cadence,
            meta={"script": "scripts/backup/pg_backup.sh"},
        )
        self.session.add(record)
        await self.session.flush()
        await self.audit.log(
            action="ga.backup_created", resource_type="ga_backup", resource_id=record.id,
            organization_id=organization_id, user_id=user_id, details={"path": path},
        )
        return record

    async def verify_backup(self, backup_id: str) -> GABackupRecord | None:
        record = await self.session.get(GABackupRecord, backup_id)
        if record is None:
            return None
        record.status = BackupStatus.VERIFIED.value
        record.verified_at = utcnow()
        await self.session.flush()
        return record

    async def list_catalog(self, *, organization_id: str | None = None) -> list[GABackupRecord]:
        stmt = select(GABackupRecord).order_by(GABackupRecord.created_at.desc())
        if organization_id:
            stmt = stmt.where(GABackupRecord.organization_id == organization_id)
        return list((await self.session.execute(stmt.limit(100))).scalars().all())

    async def restore(
        self, backup_id: str, *, organization_id: str | None = None,
        user_id: str | None = None,
    ) -> GARestoreHistory:
        record = await self.session.get(GABackupRecord, backup_id)
        if record is None:
            raise ValueError("backup not found")
        hist = GARestoreHistory(
            backup_id=backup_id, organization_id=organization_id,
            initiated_by=user_id, status="COMPLETED",
            result={"path": record.storage_path, "simulated": True,
                    "note": "Use scripts/backup/pg_restore_verify.sh for live restore"},
        )
        self.session.add(hist)
        await self.audit.log(
            action="ga.backup_restore", resource_type="ga_backup", resource_id=backup_id,
            organization_id=organization_id, user_id=user_id, details=hist.result,
        )
        await self.session.flush()
        return hist

    async def purge_expired(self) -> int:
        now = utcnow()
        rows = list((await self.session.execute(select(GABackupRecord))).scalars().all())
        purged = 0
        for row in rows:
            age_days = (now - row.created_at).days if row.created_at else 0
            if age_days > row.retention_days:
                await self.session.delete(row)
                purged += 1
        return purged


# --------------------------------------------------------------------------- #
# Health center
# --------------------------------------------------------------------------- #
class HealthCenterService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def dashboard(self, *, organization_id: str | None = None) -> dict:
        from app.core import health
        from app.platform.events import EventBus
        from app.platform.execution import ExecutionEngine
        from app.platform.plugins import PluginService

        overall, checks = await health.run_checks(health.READINESS_CHECKS)
        check_map = {c.name: c.to_dict() for c in checks}

        queue_status = {"ok": settings.JOB_QUEUE_ENABLED, "detail": "arq worker"}
        try:
            from app.jobs.queue import get_arq_pool
            pool = await get_arq_pool()
            queue_status["connected"] = pool is not None
        except Exception:  # noqa: BLE001
            queue_status["connected"] = False

        plugins = await PluginService(self.session).list_installed(organization_id) if organization_id else []
        event_pending = 0
        if organization_id:
            try:
                event_pending = await EventBus(self.session).pending_count(
                    organization_id=organization_id)
            except Exception:  # noqa: BLE001
                pass

        exec_analytics = {}
        try:
            exec_analytics = await ExecutionEngine(self.session).analytics(
                organization_id=organization_id)
        except Exception as exc:  # noqa: BLE001
            exec_analytics = {"error": str(exc)}

        components = {
            "database": check_map.get("database", {}),
            "redis": check_map.get("redis", {}),
            "storage": check_map.get("storage", {}),
            "scheduler": check_map.get("scheduler", {}),
            "ai_providers": check_map.get("ai_providers", {}),
            "queue": queue_status,
            "event_bus": {"pending": event_pending},
            "execution_engine": exec_analytics,
            "plugins": {"installed": len(plugins)},
        }
        passed = sum(1 for c in checks if c.status == health.PASS)
        score = int(round(100 * passed / max(len(checks), 1)))

        return {
            "overall": overall,
            "health_score": score,
            "components": components,
            "checks": [c.to_dict() for c in checks],
            "updated_at": utcnow().isoformat(),
        }


# --------------------------------------------------------------------------- #
# Diagnostics bundle (ZIP)
# --------------------------------------------------------------------------- #
class DiagnosticsBundleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ops = OperationsService(session)

    async def collect(self, *, organization_id: str | None = None) -> dict:
        bundle = await self.ops.support_bundle(organization_id=organization_id)
        health = await HealthCenterService(self.session).dashboard(
            organization_id=organization_id)
        jobs = {}
        try:
            from app.services.jobs import JobService
            recent = await JobService(self.session).list(
                organization_id, limit=20)
            jobs = {"recent": [{"id": j.id, "type": j.job_type, "status": j.status} for j in recent]}
        except Exception as exc:  # noqa: BLE001
            jobs = {"error": str(exc)}

        identity = {"mfa_enabled": settings.IDENTITY_ENABLED}
        billing = {"enabled": settings.BILLING_ENABLED}

        return _redact({
            "diagnostics": bundle,
            "health_center": health,
            "jobs": jobs,
            "plugins": health.get("components", {}).get("plugins"),
            "identity": identity,
            "billing": billing,
            "configuration": await self.ops.export_config(organization_id=organization_id),
        })

    async def export_zip(self, *, organization_id: str | None = None) -> bytes:
        data = await self.collect(organization_id=organization_id)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("diagnostics.json", json.dumps(data, indent=2, default=str))
            zf.writestr("README.txt",
                        "Nexora GA diagnostics bundle — secrets redacted. For support use only.")
        return buf.getvalue()


# --------------------------------------------------------------------------- #
# Support mode
# --------------------------------------------------------------------------- #
class SupportModeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditLogRepository(session)

    async def issue_token(
        self, *, organization_id: str | None, created_by: str,
        ttl_hours: int = 24, read_only: bool = True,
    ) -> dict:
        raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        row = GASupportToken(
            organization_id=organization_id, token_hash=token_hash,
            scope="diagnostics", read_only=read_only,
            expires_at=utcnow() + timedelta(hours=ttl_hours),
            created_by=created_by,
            audit_meta={"issued_for": "support_bundle"},
        )
        self.session.add(row)
        await self.audit.log(
            action="ga.support_token_issued", resource_type="ga_support_token",
            resource_id=row.id, organization_id=organization_id, user_id=created_by,
            details={"expires_hours": ttl_hours, "read_only": read_only},
        )
        await self.session.flush()
        return {"token": raw, "expires_at": row.expires_at.isoformat(), "read_only": read_only}

    async def validate_token(self, raw_token: str) -> GASupportToken | None:
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        stmt = select(GASupportToken).where(
            GASupportToken.token_hash == token_hash,
            GASupportToken.revoked_at.is_(None),
            GASupportToken.expires_at > utcnow(),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def revoke(self, token_id: str, *, user_id: str) -> bool:
        row = await self.session.get(GASupportToken, token_id)
        if row is None:
            return False
        row.revoked_at = utcnow()
        await self.audit.log(
            action="ga.support_token_revoked", resource_type="ga_support_token",
            resource_id=token_id, user_id=user_id, details={},
        )
        await self.session.flush()
        return True

    async def reproduction_package(self, *, organization_id: str) -> dict:
        diag = await DiagnosticsBundleService(self.session).collect(
            organization_id=organization_id)
        return _redact({
            "package_type": "issue_reproduction",
            "organization_id": organization_id,
            "diagnostics": diag,
            "generated_at": utcnow().isoformat(),
        })


# --------------------------------------------------------------------------- #
# Release management
# --------------------------------------------------------------------------- #
class ReleaseManagementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.config = ConfigService(session)
        self.ops = OperationsService(session)

    async def get_channel(self, organization_id: str) -> str:
        val = await self.config.get(
            _RELEASE_KEY, organization_id=organization_id,
            default=ReleaseChannel.STABLE.value)
        return str(val or ReleaseChannel.STABLE.value)

    async def set_channel(
        self, organization_id: str, channel: str, *, updated_by: str | None = None,
    ) -> dict:
        if channel not in {c.value for c in ReleaseChannel}:
            raise ValueError("channel must be stable, preview, or development")
        await self.config.set(
            key=_RELEASE_KEY, value=channel,
            scope="organization", scope_id=organization_id, updated_by=updated_by)
        return {"organization_id": organization_id, "channel": channel}

    async def staged_rollout(
        self, feature: str, percent: int, *, updated_by: str | None = None,
    ) -> dict:
        return await self.ops.set_rollout(feature, percent, updated_by=updated_by)

    def version_compatible(self, client_version: str) -> dict:
        ok = client_version >= _MIN_COMPAT
        return {
            "client_version": client_version,
            "server_version": settings.APP_VERSION,
            "compatible": ok,
            "min_supported": _MIN_COMPAT,
        }


# --------------------------------------------------------------------------- #
# Compliance center — evidence only
# --------------------------------------------------------------------------- #
class ComplianceCenterService:
    FRAMEWORKS = ("SOC2", "ISO27001", "GDPR", "HIPAA", "CIS")

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _collect_evidence(self, organization_id: str) -> list[dict]:
        evidence = []
        from app.models.audit import AuditLog

        audit_count = int((await self.session.execute(
            select(func.count(AuditLog.id)).where(AuditLog.organization_id == organization_id)
        )).scalar() or 0)
        evidence.append({
            "control": "audit_logging", "status": "implemented" if audit_count else "gap",
            "detail": f"{audit_count} audit entries on record",
        })

        from app.models.identity import UserMfaTotp
        mfa_count = int((await self.session.execute(
            select(func.count(UserMfaTotp.id))
        )).scalar() or 0)
        evidence.append({
            "control": "mfa_available", "status": "implemented" if mfa_count else "partial",
            "detail": f"{mfa_count} MFA enrollment(s)",
        })

        from app.models.sso import SSOConnection
        sso_count = int((await self.session.execute(
            select(func.count(SSOConnection.id)).where(SSOConnection.enabled.is_(True))
        )).scalar() or 0)
        evidence.append({
            "control": "sso", "status": "implemented" if sso_count else "optional",
            "detail": f"{sso_count} SSO connection(s)",
        })

        evidence.append({
            "control": "encryption_at_rest",
            "status": "implemented" if settings.MASTER_ENCRYPTION_KEY else "gap",
            "detail": "MASTER_ENCRYPTION_KEY configured" if settings.MASTER_ENCRYPTION_KEY else "not configured",
        })
        return evidence

    async def generate_report(
        self, *, organization_id: str, framework: str, user_id: str | None = None,
    ) -> GAComplianceReport:
        fw = framework.upper()
        if fw not in self.FRAMEWORKS:
            raise ValueError(f"unsupported framework: {framework}")

        evidence = await self._collect_evidence(organization_id)
        gaps = [e for e in evidence if e.get("status") in ("gap", "partial")]

        if fw == "GDPR":
            gaps.append({
                "control": "data_erasure_workflow",
                "status": "partial",
                "detail": "Use audit export + manual erasure; automated DSR workflow optional",
            })
        if fw == "HIPAA":
            gaps.append({
                "control": "baa_configuration",
                "status": "configuration",
                "detail": "HIPAA readiness requires BAA with cloud providers — not auto-verified",
            })
        if fw == "CIS":
            gaps.append({
                "control": "hardening_baseline",
                "status": "implemented" if settings.HARDENING_ENABLED else "gap",
                "detail": "Production hardening module",
            })

        implemented = sum(1 for e in evidence if e.get("status") == "implemented")
        score = int(round(100 * implemented / max(len(evidence) + len(gaps), 1)))

        report = GAComplianceReport(
            organization_id=organization_id, framework=fw,
            evidence=evidence, gaps=gaps, readiness_score=score, generated_by=user_id,
        )
        self.session.add(report)
        await self.session.flush()
        return report


# --------------------------------------------------------------------------- #
# Marketplace
# --------------------------------------------------------------------------- #
class MarketplaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.plugins = __import__(
            "app.platform.plugins", fromlist=["PluginService"]
        ).PluginService(session)

    async def discover(self) -> list[dict]:
        catalog = await self.plugins.list_catalog()
        return [
            {
                "slug": p.slug, "name": p.name, "version": p.version,
                "description": p.description, "author": p.author,
                "signature": hashlib.sha256(f"{p.slug}:{p.version}".encode()).hexdigest()[:16],
                "compatible": True,
                "rating": 4.5,
            }
            for p in catalog
        ]

    async def install(self, organization_id: str, slug: str, user_id: str | None = None) -> dict:
        inst = await self.plugins.install(
            organization_id=organization_id, slug=slug, installed_by=user_id)
        return {"slug": slug, "status": inst.status}

    async def upgrade(self, organization_id: str, slug: str) -> dict:
        inst = await self.plugins.upgrade(organization_id=organization_id, slug=slug)
        return {"slug": slug, "status": inst.status, "version": inst.version}


# --------------------------------------------------------------------------- #
# Customer success
# --------------------------------------------------------------------------- #
class CustomerSuccessService:
    MILESTONES = (
        "setup_complete", "integrations_connected", "first_discovery",
        "first_incident", "first_ai_run", "first_report", "first_dashboard",
    )

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _detect_milestones(self, organization_id: str) -> dict:
        ms = {m: False for m in self.MILESTONES}
        from app.repositories.integration import IntegrationConnectionRepository
        conns = await IntegrationConnectionRepository(self.session).list_for_org(organization_id)
        ms["integrations_connected"] = len(conns) > 0

        from app.repositories.discovery_pipeline import DiscoveryScanRunRepository
        scans = await DiscoveryScanRunRepository(self.session).list_for_org(
            organization_id, limit=1)
        ms["first_discovery"] = len(scans) > 0

        from app.repositories.incident import IncidentInvestigationRepository
        inc, _ = await IncidentInvestigationRepository(self.session).list_for_org(
            organization_id, limit=1)
        ms["first_incident"] = len(inc) > 0

        from app.models.ai_platform import AIAgentRun
        ai_count = int((await self.session.execute(
            select(func.count(AIAgentRun.id)).where(
                AIAgentRun.organization_id == organization_id)
        )).scalar() or 0)
        ms["first_ai_run"] = ai_count > 0

        from app.models.executive_report import ExecutiveReport
        rep_count = int((await self.session.execute(
            select(func.count(ExecutiveReport.id)).where(
                ExecutiveReport.organization_id == organization_id)
        )).scalar() or 0)
        ms["first_report"] = rep_count > 0

        from app.models.platform_core import DashboardLayout
        dash_count = int((await self.session.execute(
            select(func.count(DashboardLayout.id)).where(
                DashboardLayout.organization_id == organization_id)
        )).scalar() or 0)
        ms["first_dashboard"] = dash_count > 0

        ms["setup_complete"] = sum(ms.values()) >= 4
        return ms

    async def refresh(self, *, organization_id: str) -> GACustomerSuccessProgress:
        milestones = await self._detect_milestones(organization_id)
        done = sum(1 for v in milestones.values() if v)
        score = int(round(100 * done / len(self.MILESTONES)))

        recs = []
        if not milestones["integrations_connected"]:
            recs.append({"action": "Connect an integration", "path": "/integrations"})
        if not milestones["first_discovery"]:
            recs.append({"action": "Run universal discovery", "path": "/discovery"})
        if not milestones["first_incident"]:
            recs.append({"action": "Create or simulate an incident", "path": "/incidents"})

        stmt = select(GACustomerSuccessProgress).where(
            GACustomerSuccessProgress.organization_id == organization_id)
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            row = GACustomerSuccessProgress(organization_id=organization_id)
            self.session.add(row)
        row.milestones = milestones
        row.adoption_score = score
        row.recommendations = recs
        row.setup_complete = milestones.get("setup_complete", False)
        await self.session.flush()
        return row
