"""Sprint 40A — data access for incident investigations + timeline steps."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident import (
    DeploymentChangeEvent,
    IncidentInvestigation,
    IncidentInvestigationStep,
    IncidentRecommendation,
    IncidentRemediationAction,
    IncidentRemediationApproval,
    IncidentTimelineEvent,
    MonitoringAlert,
    MonitoringAlertStatus,
)
from app.repositories.base import BaseRepository


class IncidentInvestigationRepository(BaseRepository[IncidentInvestigation]):
    def __init__(self, session: AsyncSession):
        super().__init__(IncidentInvestigation, session)

    async def get_for_org(
        self, investigation_id: str, organization_id: str
    ) -> IncidentInvestigation | None:
        stmt = select(IncidentInvestigation).where(
            IncidentInvestigation.id == investigation_id,
            IncidentInvestigation.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(
        self, organization_id: str, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[IncidentInvestigation], int]:
        filters = [IncidentInvestigation.organization_id == organization_id]
        base = select(IncidentInvestigation).where(*filters)
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            await self.session.execute(
                base.order_by(IncidentInvestigation.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)


class IncidentInvestigationStepRepository(BaseRepository[IncidentInvestigationStep]):
    def __init__(self, session: AsyncSession):
        super().__init__(IncidentInvestigationStep, session)

    async def list_for_investigation(
        self, investigation_id: str, organization_id: str
    ) -> list[IncidentInvestigationStep]:
        stmt = (
            select(IncidentInvestigationStep)
            .where(
                IncidentInvestigationStep.investigation_id == investigation_id,
                IncidentInvestigationStep.organization_id == organization_id,
            )
            .order_by(IncidentInvestigationStep.step_order.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class IncidentTimelineEventRepository(BaseRepository[IncidentTimelineEvent]):
    """Sprint 40B — chronological, read-only timeline events for correlation."""

    def __init__(self, session: AsyncSession):
        super().__init__(IncidentTimelineEvent, session)

    async def list_for_investigation(
        self, investigation_id: str, organization_id: str
    ) -> list[IncidentTimelineEvent]:
        stmt = (
            select(IncidentTimelineEvent)
            .where(
                IncidentTimelineEvent.investigation_id == investigation_id,
                IncidentTimelineEvent.organization_id == organization_id,
            )
            .order_by(IncidentTimelineEvent.event_timestamp.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class DeploymentChangeEventRepository(BaseRepository[DeploymentChangeEvent]):
    """Sprint 40C — read-only deployment/change events for change correlation."""

    def __init__(self, session: AsyncSession):
        super().__init__(DeploymentChangeEvent, session)

    async def list_for_investigation(
        self, investigation_id: str, organization_id: str
    ) -> list[DeploymentChangeEvent]:
        stmt = (
            select(DeploymentChangeEvent)
            .where(
                DeploymentChangeEvent.investigation_id == investigation_id,
                DeploymentChangeEvent.organization_id == organization_id,
            )
            .order_by(DeploymentChangeEvent.change_timestamp.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class IncidentRecommendationRepository(BaseRepository[IncidentRecommendation]):
    """Sprint 41A — ranked, recommendation-only remediation suggestions."""

    def __init__(self, session: AsyncSession):
        super().__init__(IncidentRecommendation, session)

    async def list_for_investigation(
        self, investigation_id: str, organization_id: str
    ) -> list[IncidentRecommendation]:
        stmt = (
            select(IncidentRecommendation)
            .where(
                IncidentRecommendation.investigation_id == investigation_id,
                IncidentRecommendation.organization_id == organization_id,
            )
            .order_by(IncidentRecommendation.recommendation_order.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class IncidentRemediationActionRepository(BaseRepository[IncidentRemediationAction]):
    """Sprint 41B — approval-gated remediation actions (org-scoped)."""

    def __init__(self, session: AsyncSession):
        super().__init__(IncidentRemediationAction, session)

    async def get_for_org(
        self, action_id: str, organization_id: str
    ) -> IncidentRemediationAction | None:
        stmt = select(IncidentRemediationAction).where(
            IncidentRemediationAction.id == action_id,
            IncidentRemediationAction.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_investigation(
        self, investigation_id: str, organization_id: str
    ) -> list[IncidentRemediationAction]:
        stmt = (
            select(IncidentRemediationAction)
            .where(
                IncidentRemediationAction.investigation_id == investigation_id,
                IncidentRemediationAction.organization_id == organization_id,
            )
            .order_by(IncidentRemediationAction.created_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_for_org(
        self, organization_id: str, *, limit: int = 500
    ) -> list[IncidentRemediationAction]:
        """All remediation actions for an organization (newest first).

        Used by Sprint 41D deployment-risk analysis to mine rollback/remediation
        history. Read-only.
        """
        stmt = (
            select(IncidentRemediationAction)
            .where(IncidentRemediationAction.organization_id == organization_id)
            .order_by(IncidentRemediationAction.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class IncidentRemediationApprovalRepository(BaseRepository[IncidentRemediationApproval]):
    """Sprint 41B — recorded human approval/rejection decisions."""

    def __init__(self, session: AsyncSession):
        super().__init__(IncidentRemediationApproval, session)

    async def list_for_action(
        self, action_id: str, organization_id: str
    ) -> list[IncidentRemediationApproval]:
        stmt = (
            select(IncidentRemediationApproval)
            .where(
                IncidentRemediationApproval.action_id == action_id,
                IncidentRemediationApproval.organization_id == organization_id,
            )
            .order_by(IncidentRemediationApproval.created_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class MonitoringAlertRepository(BaseRepository[MonitoringAlert]):
    """Sprint 42A — normalized, deduplicated monitoring alerts (org-scoped)."""

    def __init__(self, session: AsyncSession):
        super().__init__(MonitoringAlert, session)

    async def get_for_org(self, alert_id: str, organization_id: str) -> MonitoringAlert | None:
        stmt = select(MonitoringAlert).where(
            MonitoringAlert.id == alert_id,
            MonitoringAlert.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(
        self,
        organization_id: str,
        *,
        status: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[MonitoringAlert], int]:
        filters = [MonitoringAlert.organization_id == organization_id]
        if status:
            filters.append(MonitoringAlert.status == status)
        base = select(MonitoringAlert).where(*filters)
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            await self.session.execute(
                base.order_by(MonitoringAlert.last_seen_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)

    async def find_recent_duplicate(
        self,
        *,
        organization_id: str,
        provider: str,
        alert_name: str,
        service: str | None,
        environment: str | None,
        since: datetime,
    ) -> MonitoringAlert | None:
        """Find an open alert that matches the dedup key and was last seen within
        the window (>= ``since``). Same provider + service + environment + alert
        name collapses onto a single incident to prevent alert storms."""
        stmt = (
            select(MonitoringAlert)
            .where(
                MonitoringAlert.organization_id == organization_id,
                MonitoringAlert.provider == provider,
                MonitoringAlert.alert_name == alert_name,
                MonitoringAlert.service.is_(service) if service is None else MonitoringAlert.service == service,
                MonitoringAlert.environment.is_(environment)
                if environment is None
                else MonitoringAlert.environment == environment,
                MonitoringAlert.status == MonitoringAlertStatus.FIRING.value,
                MonitoringAlert.last_seen_at >= since,
            )
            .order_by(MonitoringAlert.last_seen_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def find_active_by_dedup_key(
        self, *, organization_id: str, dedup_key: str
    ) -> MonitoringAlert | None:
        """Return the single active (FIRING) alert for a dedup identity, if any.

        Used to recover after a concurrent-insert IntegrityError raised by the
        partial-unique index ``uq_monitoring_alerts_active_dedup``.
        """
        stmt = (
            select(MonitoringAlert)
            .where(
                MonitoringAlert.organization_id == organization_id,
                MonitoringAlert.dedup_key == dedup_key,
                MonitoringAlert.status == MonitoringAlertStatus.FIRING.value,
            )
            .order_by(MonitoringAlert.last_seen_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
