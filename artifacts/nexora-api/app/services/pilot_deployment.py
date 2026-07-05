"""Pilot deployment readiness and internal dry-run support (Sprint 67E)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import ForbiddenError
from app.core.health import check_database, run_checks
from app.database import migration_check as mc
from app.models.user import User
from app.pilot.customer_portal import sanitize_customer_view
from app.pilot.deployment_readiness import (
    EXPECTED_MIGRATION_HEAD,
    _INSECURE_JWT_MARKERS,
    evaluate_pilot_deployment_readiness,
)
from app.platform.events import DomainEventType, emit_event
from app.services.pilot_operations import PilotOperationsService
from app.tenancy.permissions import can_read_resources


def _artifact_search_dirs() -> list[Path]:
    dirs: list[Path] = []
    seen: set[str] = set()
    for key in ("PILOT_67G_ARTIFACT_DIR", "PILOT_67F_ARTIFACT_DIR", "PILOT_67E_ARTIFACT_DIR"):
        val = os.environ.get(key)
        if val and val not in seen:
            dirs.append(Path(val))
            seen.add(val)
    default = Path(__file__).resolve().parents[2] / "artifacts"
    for sub in (
        "customer-pilot-alert-notification-validation",
        "customer-pilot-staging-go-live-validation",
        "pilot-deployment-readiness",
    ):
        candidate = default / sub
        if str(candidate) not in seen:
            dirs.append(candidate)
            seen.add(str(candidate))
    return dirs


def _artifact_path(name: str) -> Path | None:
    for directory in _artifact_search_dirs():
        path = directory / name
        if path.is_file():
            return path
    return None


class PilotDeploymentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.operations = PilotOperationsService(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        if not can_read_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    def _load_json_artifact(self, filename: str) -> dict | None:
        path = _artifact_path(filename)
        if not path:
            return None
        try:
            import json
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _alert_delivery_verified(self) -> bool:
        for name in ("alert-receiver-receipt.json", "alert-delivery-validation.json"):
            data = self._load_json_artifact(name) or {}
            if data.get("delivered") is True or data.get("status") == "DELIVERED":
                return True
        return False

    def _smtp_delivery_verified(self) -> bool:
        data = self._load_json_artifact("smtp-validation.json") or {}
        if data.get("status") == "DELIVERED" or data.get("email_delivery") == "DELIVERED":
            return True
        return False

    async def gather_deployment_payload(self) -> dict:
        ops_payload = await self.operations.gather_operations_payload()
        head = mc.get_head_revision()
        current = await mc.get_current_revision()
        heads = mc.get_heads()

        overall, results = await run_checks([check_database])
        health_ok = overall in ("ok", "degraded")
        health_detail = ", ".join(
            f"{r.name}={r.status}" for r in results
        ) or "database check complete"

        jwt_key = settings.JWT_SECRET_KEY or ""
        insecure_jwt = jwt_key.lower() in _INSECURE_JWT_MARKERS or jwt_key == "your-super-secret-key-change-in-production"

        dry_run = self._load_json_artifact("portal-dry-run.json") or {}
        backup = self._load_json_artifact("backup-restore-validation.json") or {}
        dry_run_completed = dry_run.get("completed") is True or dry_run.get("passed") is True
        dry_run_passed = dry_run.get("passed") is True

        webhook = settings.PILOT_ALERT_WEBHOOK_URL or os.environ.get("PILOT_ALERT_WEBHOOK_URL")
        alert_email = settings.PILOT_ALERT_EMAIL or os.environ.get("PILOT_ALERT_EMAIL")

        return {
            "app_version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "migration_head": head,
            "migration_current": current,
            "alembic_head_count": len(heads),
            "operations_payload": ops_payload,
            "pilot_mode_enabled": settings.PILOT_MODE_ENABLED,
            "pilot_mode_all_orgs": settings.PILOT_MODE_ALL_ORGS,
            "pilot_organization_ids": list(settings.PILOT_ORGANIZATION_IDS or []),
            "debug_enabled": settings.DEBUG,
            "insecure_jwt_secret": insecure_jwt,
            "cors_origins": list(settings.CORS_ALLOWED_ORIGINS or []),
            "rate_limit_enabled": settings.RATE_LIMIT_ENABLED,
            "metrics_enabled": getattr(settings, "METRICS_ENABLED", True),
            "health_ok": health_ok,
            "health_detail": health_detail,
            "email_notifications_enabled": settings.PILOT_EMAIL_NOTIFICATIONS_ENABLED,
            "smtp_configured": bool(settings.SMTP_HOST),
            "smtp_delivery_verified": self._smtp_delivery_verified(),
            "alert_receiver_configured": bool(webhook or alert_email),
            "alert_delivery_verified": self._alert_delivery_verified(),
            "backup_manifest_valid": backup.get("valid"),
            "dry_run_completed": dry_run_completed,
            "dry_run_passed": dry_run_passed,
            "dry_run_detail": dry_run.get("summary") or ("portal dry run passed" if dry_run_passed else None),
        }

    async def get_deployment_readiness(self, user: User, org_context: OrgContext) -> dict:
        self._ensure_read(user, org_context)
        payload = await self.gather_deployment_payload()
        result = evaluate_pilot_deployment_readiness(payload)
        await emit_event(
            self.session, DomainEventType.CUSTOMER_PILOT_DEPLOYMENT_READINESS_EVALUATED,
            organization_id=org_context.organization_id,
            payload=sanitize_customer_view({
                "verdict": result["verdict"],
                "migration_head": EXPECTED_MIGRATION_HEAD,
            }),
        )
        from app.observability import metrics
        metrics.set_customer_pilot_deployment_healthy(1 if result["verdict"] == "GO" else 0)
        return result

    def get_dry_run_status(self) -> dict:
        dry_run = self._load_json_artifact("portal-dry-run.json") or {}
        return sanitize_customer_view({
            "completed": dry_run.get("completed", False),
            "passed": dry_run.get("passed", False),
            "summary": dry_run.get("summary"),
            "steps": dry_run.get("steps", []),
            "evaluated_at": dry_run.get("evaluated_at"),
            "internal_only": True,
        })
