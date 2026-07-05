"""Sprint 56C — documentation verification audit trail.

Runs a verification pass and emits organization-scoped audit events. The audit
events are persisted via the existing ``AuditLogRepository`` (organization id is
recorded in ``details``). Read of the verification metrics themselves is
deterministic and side-effect free; only this run records audit history.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.repositories.audit import AuditLogRepository
from app.services.documentation_release_gate import DocumentationReleaseGateService
from app.services.documentation_verification import DocumentationVerificationService
from app.services.journey_verification import JourneyVerificationService
from app.services.navigation_validation import NavigationValidationService
from app.services.screenshot_drift import ScreenshotDriftService

RESOURCE_TYPE = "documentation_verification"


class DocumentationVerificationAuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditLogRepository(session)
        self.verification = DocumentationVerificationService()
        self.drift = ScreenshotDriftService()
        self.navigation = NavigationValidationService()
        self.journey = JourneyVerificationService()
        self.gate = DocumentationReleaseGateService()

    async def _log(self, action: str, *, org_id: str | None, user_id: str | None,
                   resource_id: str | None = None, details: dict[str, Any] | None = None) -> None:
        payload = {"organization_id": org_id, **(details or {})}
        await self.audit.log(
            action=action, resource_type=RESOURCE_TYPE,
            resource_id=resource_id, user_id=user_id, details=payload,
        )

    async def run(self, *, org_id: str | None, user_id: str | None) -> dict[str, Any]:
        records = self.verification.verifications()["items"]
        summary = self.verification.summary()
        verified = summary["verified_screenshots"]
        outdated = [r for r in records if r["verification_status"] == "OUTDATED"]
        broken = [r for r in records if r["verification_status"] == "BROKEN"]

        await self._log("screenshot_verified", org_id=org_id, user_id=user_id,
                        details={"count": verified})
        for r in outdated:
            await self._log("screenshot_outdated", org_id=org_id, user_id=user_id,
                            resource_id=r["screenshot_id"], details={"module": r["module"]})
        for r in broken:
            await self._log("screenshot_broken", org_id=org_id, user_id=user_id,
                            resource_id=r["screenshot_id"], details={"module": r["module"]})

        drift = self.drift.report()
        for item in drift["items"]:
            await self._log("drift_detected", org_id=org_id, user_id=user_id,
                            resource_id=item["affected_module"],
                            details={"severity": item["severity"]})

        nav = self.navigation.report()
        await self._log("navigation_verified", org_id=org_id, user_id=user_id,
                        details={"health_score": nav["health_score"]})

        journey = self.journey.report()
        for j in journey["journeys"]:
            await self._log("journey_verified", org_id=org_id, user_id=user_id,
                            resource_id=j["key"], details={"status": j["status"]})

        gate = self.gate.report()
        await self._log("release_gate_evaluated", org_id=org_id, user_id=user_id,
                        details={"release_ready": gate["release_ready"]})

        return {
            "verification": summary,
            "drift": drift,
            "navigation": nav,
            "journey": journey,
            "release": gate,
            "events_recorded": (
                1 + len(outdated) + len(broken) + len(drift["items"])
                + 1 + len(journey["journeys"]) + 1
            ),
        }

    async def trail(self, *, org_id: str | None, limit: int = 50) -> dict[str, Any]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.resource_type == RESOURCE_TYPE)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        items = [
            {
                "action": r.action,
                "resource_id": r.resource_id,
                "details": r.details,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
            if (r.details or {}).get("organization_id") == org_id
        ]
        return {"items": items, "total": len(items)}
