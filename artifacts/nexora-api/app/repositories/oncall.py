"""Sprint 42B — data access for on-call & escalation."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oncall import (
    EscalationEvent,
    EscalationPolicy,
    EscalationStep,
    IncidentAssignment,
    IncidentAssignmentState,
    OnCallSchedule,
    ServiceOwner,
)
from app.repositories.base import BaseRepository


class ServiceOwnerRepository(BaseRepository[ServiceOwner]):
    def __init__(self, session: AsyncSession):
        super().__init__(ServiceOwner, session)

    async def get_for_org(self, owner_id: str, organization_id: str) -> ServiceOwner | None:
        stmt = select(ServiceOwner).where(
            ServiceOwner.id == owner_id, ServiceOwner.organization_id == organization_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(self, organization_id: str) -> list[ServiceOwner]:
        stmt = (
            select(ServiceOwner)
            .where(ServiceOwner.organization_id == organization_id)
            .order_by(ServiceOwner.service_name.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def find_by_service(self, organization_id: str, service_name: str) -> ServiceOwner | None:
        stmt = (
            select(ServiceOwner)
            .where(
                ServiceOwner.organization_id == organization_id,
                ServiceOwner.service_name == service_name,
            )
            .order_by(ServiceOwner.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class OnCallScheduleRepository(BaseRepository[OnCallSchedule]):
    def __init__(self, session: AsyncSession):
        super().__init__(OnCallSchedule, session)

    async def get_for_org(self, schedule_id: str, organization_id: str) -> OnCallSchedule | None:
        stmt = select(OnCallSchedule).where(
            OnCallSchedule.id == schedule_id, OnCallSchedule.organization_id == organization_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(
        self, organization_id: str, *, active_only: bool = False
    ) -> list[OnCallSchedule]:
        filters = [OnCallSchedule.organization_id == organization_id]
        if active_only:
            filters.append(OnCallSchedule.is_active.is_(True))
        stmt = select(OnCallSchedule).where(*filters).order_by(OnCallSchedule.created_at.asc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def find_for_team(self, organization_id: str, team: str) -> OnCallSchedule | None:
        stmt = (
            select(OnCallSchedule)
            .where(
                OnCallSchedule.organization_id == organization_id,
                OnCallSchedule.team == team,
                OnCallSchedule.is_active.is_(True),
            )
            .order_by(OnCallSchedule.created_at.asc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class EscalationPolicyRepository(BaseRepository[EscalationPolicy]):
    def __init__(self, session: AsyncSession):
        super().__init__(EscalationPolicy, session)

    async def get_for_org(self, policy_id: str, organization_id: str) -> EscalationPolicy | None:
        stmt = select(EscalationPolicy).where(
            EscalationPolicy.id == policy_id, EscalationPolicy.organization_id == organization_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(self, organization_id: str) -> list[EscalationPolicy]:
        stmt = (
            select(EscalationPolicy)
            .where(EscalationPolicy.organization_id == organization_id)
            .order_by(EscalationPolicy.created_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def find_for_service(
        self, organization_id: str, service_name: str | None
    ) -> EscalationPolicy | None:
        # Prefer a service-specific active policy, else the org default (NULL service).
        if service_name:
            stmt = (
                select(EscalationPolicy)
                .where(
                    EscalationPolicy.organization_id == organization_id,
                    EscalationPolicy.service_name == service_name,
                    EscalationPolicy.is_active.is_(True),
                )
                .order_by(EscalationPolicy.created_at.desc())
                .limit(1)
            )
            found = (await self.session.execute(stmt)).scalar_one_or_none()
            if found:
                return found
        stmt = (
            select(EscalationPolicy)
            .where(
                EscalationPolicy.organization_id == organization_id,
                EscalationPolicy.service_name.is_(None),
                EscalationPolicy.is_active.is_(True),
            )
            .order_by(EscalationPolicy.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class EscalationStepRepository(BaseRepository[EscalationStep]):
    def __init__(self, session: AsyncSession):
        super().__init__(EscalationStep, session)

    async def list_for_policy(self, policy_id: str, organization_id: str) -> list[EscalationStep]:
        stmt = (
            select(EscalationStep)
            .where(
                EscalationStep.policy_id == policy_id,
                EscalationStep.organization_id == organization_id,
            )
            .order_by(EscalationStep.step_order.asc(), EscalationStep.after_minutes.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class IncidentAssignmentRepository(BaseRepository[IncidentAssignment]):
    def __init__(self, session: AsyncSession):
        super().__init__(IncidentAssignment, session)

    async def get_for_org(self, assignment_id: str, organization_id: str) -> IncidentAssignment | None:
        stmt = select(IncidentAssignment).where(
            IncidentAssignment.id == assignment_id,
            IncidentAssignment.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_for_incident(
        self, incident_id: str, organization_id: str
    ) -> IncidentAssignment | None:
        stmt = select(IncidentAssignment).where(
            IncidentAssignment.incident_id == incident_id,
            IncidentAssignment.organization_id == organization_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_org(self, organization_id: str, *, limit: int = 500) -> list[IncidentAssignment]:
        stmt = (
            select(IncidentAssignment)
            .where(IncidentAssignment.organization_id == organization_id)
            .order_by(IncidentAssignment.assigned_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_unresolved(self, organization_id: str | None = None) -> list[IncidentAssignment]:
        filters = [
            IncidentAssignment.state.in_(
                [IncidentAssignmentState.OPEN.value, IncidentAssignmentState.INVESTIGATING.value]
            )
        ]
        if organization_id:
            filters.append(IncidentAssignment.organization_id == organization_id)
        stmt = select(IncidentAssignment).where(*filters)
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_open_unacknowledged(self) -> list[IncidentAssignment]:
        """All assignments (any org) still awaiting acknowledgement — used by the
        escalation scheduler."""
        stmt = select(IncidentAssignment).where(
            IncidentAssignment.state == IncidentAssignmentState.OPEN.value,
            IncidentAssignment.acknowledged_at.is_(None),
        )
        return list((await self.session.execute(stmt)).scalars().all())


class EscalationEventRepository(BaseRepository[EscalationEvent]):
    def __init__(self, session: AsyncSession):
        super().__init__(EscalationEvent, session)

    async def list_for_incident(self, incident_id: str, organization_id: str) -> list[EscalationEvent]:
        stmt = (
            select(EscalationEvent)
            .where(
                EscalationEvent.incident_id == incident_id,
                EscalationEvent.organization_id == organization_id,
            )
            .order_by(EscalationEvent.notified_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_for_org(self, organization_id: str, *, limit: int = 100) -> tuple[list[EscalationEvent], int]:
        stmt = (
            select(EscalationEvent)
            .where(EscalationEvent.organization_id == organization_id)
            .order_by(EscalationEvent.notified_at.desc())
            .limit(limit)
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        return rows, len(rows)
