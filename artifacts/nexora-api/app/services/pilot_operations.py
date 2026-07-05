"""Pilot operations readiness and support diagnostics (Sprint 67D)."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.config import settings
from app.core.exceptions import ForbiddenError, ValidationError
from app.database import migration_check as mc
from app.integration_readiness.evidence import redact_text
from app.models.audit import AuditLog
from app.models.customer_pilot import PilotSchedulerHealthSnapshot
from app.models.job import Job, JobType
from app.models.organization import Organization
from app.models.pilot import PilotApproval, PilotEnrollment, PilotLiveOperation
from app.models.user import User
from app.pilot.customer_portal import assert_export_safe, sanitize_customer_view
from app.pilot.operations_readiness import (
    customer_safe_operations_status,
    evaluate_pilot_operations_readiness,
)
from app.platform.events import DomainEventType, emit_event
from app.repositories.audit import AuditLogRepository
from app.repositories.pilot import PilotEnrollmentRepo
from app.services.customer_pilot_timeline import CustomerPilotTimelineService
from app.services.document_export import render_pdf
from app.services.pilot import PilotService
from app.services.pilot_notification_delivery import PilotNotificationDeliveryService
from app.tenancy.permissions import can_read_resources


REMINDER_JOB = JobType.CRON_CUSTOMER_PILOT_APPROVAL_REMINDERS.value


class PilotOperationsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.pilot = PilotService(session)
        self.enrollments = PilotEnrollmentRepo(session)
        self.deliveries = PilotNotificationDeliveryService(session)
        self.audit = AuditLogRepository(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        if not can_read_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    async def _redis_available(self) -> bool:
        try:
            from app.redis.client import get_redis

            client = await get_redis()
            if client is None:
                return not settings.DISTRIBUTED_LOCK_ENABLED
            await client.ping()
            return True
        except Exception:
            return False

    async def _worker_recent(self) -> tuple[bool, str]:
        if not settings.JOB_QUEUE_ENABLED:
            return True, "Job queue disabled — in-process mode"
        cutoff = datetime.now(UTC) - timedelta(hours=2)
        row = (await self.session.execute(
            select(Job).where(
                Job.job_type == REMINDER_JOB,
                Job.status == "COMPLETED",
                Job.finished_at >= cutoff,
            ).order_by(Job.finished_at.desc()).limit(1),
        )).scalar_one_or_none()
        if row:
            return True, f"Last reminder job completed at {row.finished_at}"
        return False, "No completed reminder job in last 2 hours"

    async def _last_scheduler_snapshot(self) -> PilotSchedulerHealthSnapshot | None:
        return (await self.session.execute(
            select(PilotSchedulerHealthSnapshot).where(
                PilotSchedulerHealthSnapshot.job_type == REMINDER_JOB,
            ).order_by(PilotSchedulerHealthSnapshot.ran_at.desc()).limit(1),
        )).scalar_one_or_none()

    async def gather_operations_payload(self) -> dict:
        redis_ok = await self._redis_available()
        worker_ok, worker_detail = await self._worker_recent()
        snapshot = await self._last_scheduler_snapshot()
        stats = await self.deliveries.delivery_stats()

        last_success = None
        consec = 0
        if snapshot and snapshot.status == "success":
            last_success = snapshot.ran_at.isoformat()
            consec = 0
        elif snapshot:
            consec = snapshot.consecutive_failures
            prev = (await self.session.execute(
                select(PilotSchedulerHealthSnapshot).where(
                    PilotSchedulerHealthSnapshot.job_type == REMINDER_JOB,
                    PilotSchedulerHealthSnapshot.status == "success",
                ).order_by(PilotSchedulerHealthSnapshot.ran_at.desc()).limit(1),
            )).scalar_one_or_none()
            if prev:
                last_success = prev.ran_at.isoformat()

        return {
            "redis_available": redis_ok,
            "worker_recent": worker_ok,
            "worker_detail": worker_detail,
            "reminder_cron_registered": settings.PILOT_MODE_ENABLED and settings.JOB_CRON_ENABLED,
            "job_queue_enabled": settings.JOB_QUEUE_ENABLED,
            "distributed_lock_enabled": settings.DISTRIBUTED_LOCK_ENABLED,
            "scheduler_lock_available": redis_ok,
            "scheduler_lock_detail": "Redis lock available" if redis_ok else "Redis lock unavailable",
            "reminder_last_success_at": last_success,
            "reminder_consecutive_failures": consec,
            "reminder_stale_hours": max(1, settings.JOB_CRON_CUSTOMER_PILOT_APPROVAL_REMINDERS_SECONDS / 60 * 3 / 60),
            "notification_queue_oldest_seconds": stats.get("oldest_queued_seconds"),
            "failed_delivery_count": stats.get("failed_count", 0),
            "clock_sane": datetime.now(UTC).tzinfo is not None,
            "email_configured": bool(settings.SMTP_HOST),
        }

    async def get_operations_readiness(self, user: User, org_context: OrgContext) -> dict:
        self._ensure_read(user, org_context)
        payload = await self.gather_operations_payload()
        result = evaluate_pilot_operations_readiness(payload)
        await emit_event(
            self.session, DomainEventType.CUSTOMER_PILOT_OPERATIONS_READINESS_EVALUATED,
            organization_id=org_context.organization_id,
            payload=sanitize_customer_view({"verdict": result["verdict"]}),
        )
        from app.observability import metrics
        metrics.set_customer_pilot_scheduler_healthy(1 if result["verdict"] == "GO" else 0)
        metrics.set_customer_pilot_worker_healthy(1 if payload.get("worker_recent") else 0)
        if result["verdict"] != "GO":
            await emit_event(
                self.session, DomainEventType.CUSTOMER_PILOT_SCHEDULER_DEGRADED,
                organization_id=org_context.organization_id,
                payload=sanitize_customer_view({"verdict": result["verdict"]}),
            )
        return result

    async def get_customer_operations_status(self, user: User, org_context: OrgContext) -> dict:
        self._ensure_read(user, org_context)
        payload = await self.gather_operations_payload()
        ops = evaluate_pilot_operations_readiness(payload)
        return customer_safe_operations_status(ops)

    async def record_scheduler_run(self, job_type: str, result: dict) -> None:
        prev = await self._last_scheduler_snapshot()
        success = not result.get("skipped") and result.get("failures", 0) == 0
        consec = 0 if success else (prev.consecutive_failures + 1 if prev else 1)
        self.session.add(PilotSchedulerHealthSnapshot(
            job_type=job_type,
            status="success" if success else "failure",
            result=sanitize_customer_view(result),
            consecutive_failures=consec,
            ran_at=datetime.now(UTC),
        ))
        await self.session.flush()

    async def build_support_bundle(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        enrollment = await self.enrollments.get_for_org(organization_id)
        launch = await self.pilot.get_launch_readiness(user, org_context)
        ops = evaluate_pilot_operations_readiness(await self.gather_operations_payload())
        stats = await self.deliveries.delivery_stats(organization_id)
        timeline = await CustomerPilotTimelineService(self.session).get_timeline(
            user, org_context, limit=30,
        )

        stages = []
        if enrollment:
            stage_rows = await self.pilot.stages.list_for_enrollment(enrollment.id)
            stages = [{
                "stage_key": s.stage_key,
                "status": s.status,
                "outcome": s.outcome,
            } for s in stage_rows]

        approvals = list((await self.session.execute(
            select(PilotApproval).where(PilotApproval.organization_id == organization_id),
        )).scalars().all())
        ops_summary = list((await self.session.execute(
            select(PilotLiveOperation).where(PilotLiveOperation.organization_id == organization_id),
        )).scalars().all())

        audit_rows = list((await self.session.execute(
            select(AuditLog).where(
                AuditLog.organization_id == organization_id,
            ).order_by(AuditLog.created_at.desc()).limit(20),
        )).scalars().all())
        safe_audit = []
        for row in audit_rows:
            if row.action.startswith(("pilot.confirmation", "integration.credential")):
                continue
            if row.action.startswith(("customer_pilot.", "pilot.", "pilot.notification")):
                safe_audit.append({
                    "action": row.action,
                    "at": row.created_at.isoformat() if row.created_at else None,
                })

        migration_rev = await mc.get_current_revision()

        org = await self.session.get(Organization, organization_id)
        bundle = sanitize_customer_view({
            "organization_name": org.name if org else "Organization",
            "generated_at": datetime.now(UTC).isoformat(),
            "enrollment": {
                "id": enrollment.id if enrollment else None,
                "status": enrollment.status if enrollment else None,
                "execution_status": enrollment.execution_status if enrollment else None,
            },
            "stages": stages,
            "launch_readiness": {
                "verdict": launch.get("verdict"),
                "failed_checks": launch.get("failed_checks"),
            },
            "operations_readiness": {
                "verdict": ops.get("verdict"),
                "failed_checks": ops.get("failed_checks"),
            },
            "notification_health": stats,
            "approval_summary": [
                {"id": a.id, "status": a.status, "operation_id": a.operation_id}
                for a in approvals
            ],
            "operation_summary": [
                {"id": o.id, "status": o.status, "verification_status": o.verification_status}
                for o in ops_summary
            ],
            "timeline_events": timeline.get("events", [])[:20],
            "audit_events": safe_audit,
            "migration_version": migration_rev,
            "feature_flags": {
                "pilot_mode_enabled": settings.PILOT_MODE_ENABLED,
                "job_cron_enabled": settings.JOB_CRON_ENABLED,
            },
        })
        await emit_event(
            self.session, DomainEventType.CUSTOMER_PILOT_SUPPORT_BUNDLE_GENERATED,
            organization_id=organization_id,
            actor_id=user.id,
            payload={"event_count": len(timeline.get("events", []))},
        )
        from app.observability import metrics
        metrics.record_customer_pilot_support_bundle()
        return bundle

    async def export_support_bundle(self, user: User, org_context: OrgContext) -> dict:
        bundle = await self.build_support_bundle(user, org_context)
        try:
            assert_export_safe(bundle)
            md_lines = [
                f"# Pilot Support Bundle — {bundle.get('organization_name')}",
                f"Generated: {bundle.get('generated_at')}",
                "",
                f"## Launch readiness: {bundle.get('launch_readiness', {}).get('verdict')}",
                f"## Operations readiness: {bundle.get('operations_readiness', {}).get('verdict')}",
                "",
            ]
            for ev in bundle.get("timeline_events", [])[:10]:
                md_lines.append(f"- {ev.get('timestamp')}: {ev.get('title')} ({ev.get('status')})")
            md = "\n".join(md_lines)
            html = f"<html><body><h1>Support Bundle</h1><pre>{redact_text(md)}</pre></body></html>"
            pdf = base64.b64encode(render_pdf(md)).decode("ascii")
            blocked, reason = False, None
        except ValidationError as exc:
            md, html, pdf = "", "", None
            blocked, reason = True, str(exc)

        return {
            "json_payload": bundle,
            "markdown": md,
            "html": html,
            "pdf_base64": pdf,
            "redacted": True,
            "export_blocked": blocked,
            "block_reason": reason,
        }
