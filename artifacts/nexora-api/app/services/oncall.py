"""Sprint 42B — Intelligent On-Call & Escalation Engine.

Three cooperating pieces, all read-only with respect to infrastructure:

* ``OnCallService`` — CRUD for service ownership, rotation schedules, and
  escalation policies, plus timezone-aware resolution of the current on-call
  engineer.
* ``IncidentRoutingService`` — when an incident is created, determine the
  affected service, its owner, and the current on-call engineer, create the
  ``IncidentAssignment`` (owner/responder/approver), and notify the responder.
* ``EscalationEngine`` — periodically advance unacknowledged incidents through
  their escalation ladder (0/10/20/30 min …) and page the next target.

Acknowledgement is explicit and stops escalation. Everything is org-scoped and
audited. No secrets are stored or notified. Remediation still requires human
approval (Sprint 41B/C) — this engine never executes anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NexoraException
from app.models.oncall import (
    EscalationTargetType,
    IncidentAssignmentState,
    OnCallRotationType,
)
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.incident import IncidentInvestigationRepository
from app.repositories.oncall import (
    EscalationEventRepository,
    EscalationPolicyRepository,
    EscalationStepRepository,
    IncidentAssignmentRepository,
    OnCallScheduleRepository,
    ServiceOwnerRepository,
)
from app.services.incident_notifications import IncidentNotificationService
from app.tenancy.permissions import can_read_ai_teams, can_write_ai_teams

logger = structlog.get_logger(__name__)

# Default escalation ladder used when no policy is configured (level 0 = on-call
# notified at routing time). Configurable via EscalationPolicy/EscalationStep.
DEFAULT_LADDER = [
    (10, EscalationTargetType.SECONDARY_OWNER.value),
    (20, EscalationTargetType.PRIMARY_OWNER.value),
]


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


@dataclass
class _Step:
    level: int
    after_minutes: int
    target_type: str
    target_user_id: str | None
    channels: str


def resolve_current_oncall(schedule, now: datetime | None = None) -> str | None:
    """Resolve the participant currently on-call for a rotation, timezone-aware."""
    participants = list(schedule.participants or [])
    if not participants:
        return None
    now = _aware(now) or _now()
    try:
        tz = ZoneInfo(schedule.timezone or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo("UTC")
    anchor = _aware(schedule.anchor_at) or now
    now_local = now.astimezone(tz)
    anchor_local = anchor.astimezone(tz)
    days = (now_local.date() - anchor_local.date()).days
    if days < 0:
        return participants[0]
    if schedule.rotation_type == OnCallRotationType.DAILY.value:
        index = days % len(participants)
    else:  # WEEKLY (default)
        index = (days // 7) % len(participants)
    return participants[index]


class OnCallService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.owner_repo = ServiceOwnerRepository(session)
        self.schedule_repo = OnCallScheduleRepository(session)
        self.policy_repo = EscalationPolicyRepository(session)
        self.step_repo = EscalationStepRepository(session)
        self.assignment_repo = IncidentAssignmentRepository(session)
        self.event_repo = EscalationEventRepository(session)
        self.audit_repo = AuditLogRepository(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    def _ensure_write(self, user: User, org_context: OrgContext) -> None:
        if not user.is_superuser and (
            not org_context.role or not can_write_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    # ----------------------------------------------------------- service owners
    async def create_service_owner(self, user, org_context, data):
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        owner = await self.owner_repo.create(
            organization_id=organization_id,
            service_name=data.service_name,
            primary_owner_id=data.primary_owner_id,
            secondary_owner_id=data.secondary_owner_id,
            team=data.team,
            escalation_group=data.escalation_group,
        )
        await self.audit_repo.log(
            action="service_owner_created",
            resource_type="service_owner",
            resource_id=owner.id,
            user_id=user.id,
            details={"organization_id": organization_id, "service_name": data.service_name},
        )
        await self.session.commit()
        return owner

    async def list_service_owners(self, user, org_context):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        return await self.owner_repo.list_for_org(organization_id)

    async def update_service_owner(self, user, org_context, owner_id, data):
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        owner = await self.owner_repo.get_for_org(owner_id, organization_id)
        if owner is None:
            raise NexoraException("Service owner not found.", status_code=404)
        for field in ("primary_owner_id", "secondary_owner_id", "team", "escalation_group"):
            value = getattr(data, field)
            if value is not None:
                setattr(owner, field, value)
        await self.audit_repo.log(
            action="service_owner_updated",
            resource_type="service_owner",
            resource_id=owner.id,
            user_id=user.id,
            details={"organization_id": organization_id},
        )
        await self.session.commit()
        return owner

    async def delete_service_owner(self, user, org_context, owner_id):
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        owner = await self.owner_repo.get_for_org(owner_id, organization_id)
        if owner is None:
            raise NexoraException("Service owner not found.", status_code=404)
        await self.session.delete(owner)
        await self.audit_repo.log(
            action="service_owner_deleted",
            resource_type="service_owner",
            resource_id=owner_id,
            user_id=user.id,
            details={"organization_id": organization_id},
        )
        await self.session.commit()

    # --------------------------------------------------------------- schedules
    async def create_schedule(self, user, org_context, data):
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        rotation = (data.rotation_type or "WEEKLY").upper()
        if rotation not in (OnCallRotationType.DAILY.value, OnCallRotationType.WEEKLY.value):
            raise NexoraException("rotation_type must be DAILY or WEEKLY.", status_code=400)
        schedule = await self.schedule_repo.create(
            organization_id=organization_id,
            name=data.name,
            team=data.team,
            rotation_type=rotation,
            timezone=data.timezone or "UTC",
            participants=list(data.participants or []),
            anchor_at=_aware(data.anchor_at) or _now(),
            is_active=data.is_active,
        )
        await self.audit_repo.log(
            action="oncall_schedule_created",
            resource_type="oncall_schedule",
            resource_id=schedule.id,
            user_id=user.id,
            details={"organization_id": organization_id, "rotation_type": rotation},
        )
        await self.session.commit()
        return schedule

    async def list_schedules(self, user, org_context):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        return await self.schedule_repo.list_for_org(organization_id)

    async def get_schedule(self, user, org_context, schedule_id):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        return await self.schedule_repo.get_for_org(schedule_id, organization_id)

    async def delete_schedule(self, user, org_context, schedule_id):
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        schedule = await self.schedule_repo.get_for_org(schedule_id, organization_id)
        if schedule is None:
            raise NexoraException("Schedule not found.", status_code=404)
        await self.session.delete(schedule)
        await self.audit_repo.log(
            action="oncall_schedule_deleted",
            resource_type="oncall_schedule",
            resource_id=schedule_id,
            user_id=user.id,
            details={"organization_id": organization_id},
        )
        await self.session.commit()

    # ----------------------------------------------------------- policies
    async def create_policy(self, user, org_context, data):
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        policy = await self.policy_repo.create(
            organization_id=organization_id,
            name=data.name,
            service_name=data.service_name,
            is_active=data.is_active,
        )
        for idx, step in enumerate(data.steps or []):
            await self.step_repo.create(
                organization_id=organization_id,
                policy_id=policy.id,
                step_order=idx,
                after_minutes=step.after_minutes,
                target_type=step.target_type.upper(),
                target_user_id=step.target_user_id,
                channels=step.channels or "slack,email",
            )
        await self.audit_repo.log(
            action="escalation_policy_created",
            resource_type="escalation_policy",
            resource_id=policy.id,
            user_id=user.id,
            details={"organization_id": organization_id, "steps": len(data.steps or [])},
        )
        await self.session.commit()
        return policy

    async def list_policies(self, user, org_context):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        policies = await self.policy_repo.list_for_org(organization_id)
        result = []
        for p in policies:
            steps = await self.step_repo.list_for_policy(p.id, organization_id)
            result.append((p, steps))
        return result

    async def policy_steps(self, organization_id, policy_id):
        return await self.step_repo.list_for_policy(policy_id, organization_id)

    async def delete_policy(self, user, org_context, policy_id):
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        policy = await self.policy_repo.get_for_org(policy_id, organization_id)
        if policy is None:
            raise NexoraException("Policy not found.", status_code=404)
        await self.session.delete(policy)
        await self.audit_repo.log(
            action="escalation_policy_deleted",
            resource_type="escalation_policy",
            resource_id=policy_id,
            user_id=user.id,
            details={"organization_id": organization_id},
        )
        await self.session.commit()

    # ----------------------------------------------------------- current on-call
    async def current_oncall(self, user, org_context):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        schedules = await self.schedule_repo.list_for_org(organization_id, active_only=True)
        return [(s, resolve_current_oncall(s)) for s in schedules]


class IncidentRoutingService:
    """Routes a new incident to its owner + current on-call engineer."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.owner_repo = ServiceOwnerRepository(session)
        self.schedule_repo = OnCallScheduleRepository(session)
        self.policy_repo = EscalationPolicyRepository(session)
        self.assignment_repo = IncidentAssignmentRepository(session)
        self.incident_repo = IncidentInvestigationRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.notifier = IncidentNotificationService(session)

    async def route_incident(
        self,
        user: User,
        org_context: OrgContext,
        incident_id: str,
        *,
        service_name: str | None,
        severity: str | None = None,
        commit: bool = True,
    ) -> tuple[object, int]:
        """Create the on-call assignment for an incident and notify the responder.

        Idempotent: returns the existing assignment if already routed. Returns
        ``(assignment, notifications_sent)``."""
        organization_id = org_context.requires_organization
        existing = await self.assignment_repo.get_for_incident(incident_id, organization_id)
        if existing is not None:
            return existing, 0

        incident = await self.incident_repo.get_for_org(incident_id, organization_id)
        title = incident.title if incident else (service_name or "Incident")
        sev = severity or (incident.severity if incident else None) or "HIGH"
        suspected_cause = None
        confidence = None
        recommended_action = None
        if incident is not None:
            suspected_cause = incident.root_cause or incident.suspected_trigger
            confidence = incident.confidence_score
            from app.repositories.incident import IncidentRecommendationRepository
            recs = await IncidentRecommendationRepository(self.session).list_for_investigation(
                incident_id, organization_id,
            )
            if recs:
                recommended_action = recs[0].title

        service_owner = (
            await self.owner_repo.find_by_service(organization_id, service_name)
            if service_name
            else None
        )

        schedule = None
        if service_owner and service_owner.team:
            schedule = await self.schedule_repo.find_for_team(organization_id, service_owner.team)
        if schedule is None:
            active = await self.schedule_repo.list_for_org(organization_id, active_only=True)
            schedule = active[0] if active else None

        oncall_user = resolve_current_oncall(schedule) if schedule else None
        primary = service_owner.primary_owner_id if service_owner else None
        owner_id = primary or oncall_user
        responder_id = oncall_user or owner_id
        approver_id = primary or owner_id

        policy = await self.policy_repo.find_for_service(organization_id, service_name)

        assignment = await self.assignment_repo.create(
            organization_id=organization_id,
            incident_id=incident_id,
            service_name=service_name,
            owner_id=owner_id,
            responder_id=responder_id,
            approver_id=approver_id,
            oncall_schedule_id=schedule.id if schedule else None,
            escalation_policy_id=policy.id if policy else None,
            state=IncidentAssignmentState.OPEN.value,
            current_level=0,
            assigned_at=_now(),
        )
        await self.audit_repo.log(
            action="incident_assigned",
            resource_type="incident_assignment",
            resource_id=assignment.id,
            user_id=user.id,
            details={
                "organization_id": organization_id,
                "incident_id": incident_id,
                "service_name": service_name,
                "owner_id": owner_id,
                "responder_id": responder_id,
                "approver_id": approver_id,
                "oncall_schedule_id": schedule.id if schedule else None,
            },
        )

        # Page the on-call responder (level 0). Fall back to a generic incident
        # notification when no responder could be resolved.
        if responder_id:
            delivered = await self.notifier.notify_recipient(
                organization_id=organization_id,
                incident_id=incident_id,
                title=title,
                severity=sev,
                reason="on-call assignment",
                recipient_user_id=responder_id,
                recipient_label="on-call engineer",
                suspected_cause=suspected_cause,
                confidence=confidence,
                recommended_action=recommended_action,
                user_id=user.id,
            )
        else:
            delivered = await self.notifier.notify_incident(
                organization_id=organization_id,
                incident_id=incident_id,
                title=title,
                severity=sev,
                suspected_cause=suspected_cause,
                confidence=confidence,
                recommended_action=recommended_action,
                user_id=user.id,
            )

        if commit:
            await self.session.commit()
        return assignment, len(delivered)

    # ---------------------------------------------------- acknowledgement flow
    async def _ensure_write(self, user, org_context):
        if not user.is_superuser and (
            not org_context.role or not can_write_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    async def acknowledge(self, user, org_context, incident_id):
        organization_id = org_context.requires_organization
        await self._ensure_write(user, org_context)
        assignment = await self.assignment_repo.get_for_incident(incident_id, organization_id)
        if assignment is None:
            raise NexoraException("Incident assignment not found.", status_code=404)
        if assignment.acknowledged_at is None:
            assignment.acknowledged_at = _now()
            assignment.acknowledged_by_id = user.id
        if assignment.state == IncidentAssignmentState.OPEN.value:
            assignment.state = IncidentAssignmentState.ACKNOWLEDGED.value
        await self.audit_repo.log(
            action="incident_acknowledged",
            resource_type="incident_assignment",
            resource_id=assignment.id,
            user_id=user.id,
            details={"organization_id": organization_id, "incident_id": incident_id},
        )
        await self.session.commit()
        return assignment

    async def set_state(self, user, org_context, incident_id, state):
        organization_id = org_context.requires_organization
        await self._ensure_write(user, org_context)
        valid = {s.value for s in IncidentAssignmentState}
        state = (state or "").upper()
        if state not in valid:
            raise NexoraException(f"Invalid state. One of {sorted(valid)}.", status_code=400)
        assignment = await self.assignment_repo.get_for_incident(incident_id, organization_id)
        if assignment is None:
            raise NexoraException("Incident assignment not found.", status_code=404)
        assignment.state = state
        if state == IncidentAssignmentState.ACKNOWLEDGED.value and assignment.acknowledged_at is None:
            assignment.acknowledged_at = _now()
            assignment.acknowledged_by_id = user.id
        if state == IncidentAssignmentState.RESOLVED.value and assignment.resolved_at is None:
            assignment.resolved_at = _now()
        await self.audit_repo.log(
            action="incident_state_changed",
            resource_type="incident_assignment",
            resource_id=assignment.id,
            user_id=user.id,
            details={"organization_id": organization_id, "incident_id": incident_id, "state": state},
        )
        # Sprint 44A — auto-generate an executive postmortem when an incident is
        # resolved. Best-effort and idempotent; never blocks the resolve flow.
        if state == IncidentAssignmentState.RESOLVED.value:
            from app.services.postmortem import PostmortemService

            await PostmortemService(self.session).auto_generate_for_incident(
                organization_id, incident_id, user.id
            )
        await self.session.commit()
        return assignment

    async def get_assignment(self, user, org_context, incident_id):
        organization_id = org_context.requires_organization
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()
        assignment = await self.assignment_repo.get_for_incident(incident_id, organization_id)
        if assignment is None:
            return None, []
        events = await EscalationEventRepository(self.session).list_for_incident(
            incident_id, organization_id
        )
        return assignment, events


class EscalationEngine:
    """Advances unacknowledged incidents through their escalation ladder."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.assignment_repo = IncidentAssignmentRepository(session)
        self.owner_repo = ServiceOwnerRepository(session)
        self.schedule_repo = OnCallScheduleRepository(session)
        self.policy_repo = EscalationPolicyRepository(session)
        self.step_repo = EscalationStepRepository(session)
        self.event_repo = EscalationEventRepository(session)
        self.incident_repo = IncidentInvestigationRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.notifier = IncidentNotificationService(session)

    async def _ladder(self, assignment) -> list[_Step]:
        if assignment.escalation_policy_id:
            rows = await self.step_repo.list_for_policy(
                assignment.escalation_policy_id, assignment.organization_id
            )
            if rows:
                return [
                    _Step(
                        level=i + 1,
                        after_minutes=r.after_minutes,
                        target_type=r.target_type,
                        target_user_id=r.target_user_id,
                        channels=r.channels,
                    )
                    for i, r in enumerate(rows)
                ]
        return [
            _Step(level=i + 1, after_minutes=m, target_type=t, target_user_id=None, channels="slack,email")
            for i, (m, t) in enumerate(DEFAULT_LADDER)
        ]

    async def _resolve_target(self, assignment, step: _Step) -> str | None:
        t = step.target_type
        if t == EscalationTargetType.ONCALL.value:
            if assignment.oncall_schedule_id:
                sched = await self.schedule_repo.get_for_org(
                    assignment.oncall_schedule_id, assignment.organization_id
                )
                if sched:
                    return resolve_current_oncall(sched)
            return assignment.responder_id
        owner = (
            await self.owner_repo.find_by_service(assignment.organization_id, assignment.service_name)
            if assignment.service_name
            else None
        )
        if t == EscalationTargetType.PRIMARY_OWNER.value:
            return (owner.primary_owner_id if owner else None) or assignment.owner_id
        if t == EscalationTargetType.SECONDARY_OWNER.value:
            return owner.secondary_owner_id if owner else None
        # TEAM_LEAD / MANAGEMENT / USER → explicit target
        return step.target_user_id

    async def process_due(self, now: datetime | None = None) -> int:
        now = _aware(now) or _now()
        assignments = await self.assignment_repo.list_open_unacknowledged()
        fired = 0
        for assignment in assignments:
            elapsed = (now - (_aware(assignment.assigned_at) or now)).total_seconds() / 60.0
            ladder = await self._ladder(assignment)
            incident = await self.incident_repo.get_for_org(
                assignment.incident_id, assignment.organization_id
            )
            title = incident.title if incident else "Incident"
            sev = (incident.severity if incident else None) or "HIGH"
            for step in ladder:
                if step.level <= assignment.current_level:
                    continue
                if step.after_minutes > elapsed:
                    continue
                target_user_id = await self._resolve_target(assignment, step)
                reason = (
                    f"escalation level {step.level} "
                    f"(no acknowledgement after {step.after_minutes}m)"
                )
                await self.event_repo.create(
                    organization_id=assignment.organization_id,
                    incident_id=assignment.incident_id,
                    assignment_id=assignment.id,
                    level=step.level,
                    after_minutes=step.after_minutes,
                    target_type=step.target_type,
                    target_user_id=target_user_id,
                    channels=step.channels,
                    reason=reason,
                    notified_at=now,
                )
                if target_user_id:
                    await self.notifier.notify_recipient(
                        organization_id=assignment.organization_id,
                        incident_id=assignment.incident_id,
                        title=title,
                        severity=sev,
                        reason=reason,
                        recipient_user_id=target_user_id,
                        recipient_label=step.target_type,
                        channels=[c.strip() for c in (step.channels or "slack,email").split(",") if c.strip()],
                        user_id=None,
                    )
                assignment.current_level = step.level
                await self.audit_repo.log(
                    action="incident_escalated",
                    resource_type="incident_assignment",
                    resource_id=assignment.id,
                    user_id=None,
                    details={
                        "organization_id": assignment.organization_id,
                        "incident_id": assignment.incident_id,
                        "level": step.level,
                        "target_type": step.target_type,
                        "target_user_id": target_user_id,
                    },
                )
                fired += 1
        await self.session.commit()
        return fired


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


class OnCallMetricsService:
    """MTTA / MTTR metrics derived from incident assignments."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.assignment_repo = IncidentAssignmentRepository(session)
        self.owner_repo = ServiceOwnerRepository(session)

    def _ensure_read(self, user, org_context):
        if not user.is_superuser and (
            not org_context.role or not can_read_ai_teams(org_context.role)
        ):
            raise ForbiddenError()

    async def metrics(self, user, org_context):
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        assignments = await self.assignment_repo.list_for_org(organization_id, limit=1000)
        owners = {o.service_name: o for o in await self.owner_repo.list_for_org(organization_id)}

        def tta(a):
            if a.acknowledged_at and a.assigned_at:
                return max(0.0, (_aware(a.acknowledged_at) - _aware(a.assigned_at)).total_seconds() / 60.0)
            return None

        def ttr(a):
            if a.resolved_at and a.assigned_at:
                return max(0.0, (_aware(a.resolved_at) - _aware(a.assigned_at)).total_seconds() / 60.0)
            return None

        org_tta = [v for v in (tta(a) for a in assignments) if v is not None]
        org_ttr = [v for v in (ttr(a) for a in assignments) if v is not None]

        by_service: dict[str, list[object]] = {}
        by_team: dict[str, list[object]] = {}
        for a in assignments:
            by_service.setdefault(a.service_name or "unknown", []).append(a)
            team = (owners.get(a.service_name).team if owners.get(a.service_name) else None) or "unassigned"
            by_team.setdefault(team, []).append(a)

        def breakdown(group: dict):
            out = []
            for key, items in group.items():
                ttas = [v for v in (tta(a) for a in items) if v is not None]
                ttrs = [v for v in (ttr(a) for a in items) if v is not None]
                out.append(
                    {
                        "key": key,
                        "mtta_minutes": _mean(ttas),
                        "mttr_minutes": _mean(ttrs),
                        "incidents": len(items),
                        "acknowledged": len(ttas),
                    }
                )
            return sorted(out, key=lambda x: x["incidents"], reverse=True)

        return {
            "organization_mtta_minutes": _mean(org_tta),
            "organization_mttr_minutes": _mean(org_ttr),
            "total_incidents": len(assignments),
            "acknowledged_incidents": len(org_tta),
            "by_service": breakdown(by_service),
            "by_team": breakdown(by_team),
        }

    async def dashboard_summary(self, organization_id: str):
        """On-call slice for the Operations Center dashboard (no permission check;
        caller already enforced read)."""
        assignments = await self.assignment_repo.list_for_org(organization_id, limit=1000)
        unack = [
            a
            for a in assignments
            if a.acknowledged_at is None and a.state != IncidentAssignmentState.RESOLVED.value
        ]
        escalated = [a for a in assignments if a.current_level > 0]
        ttas = []
        for a in assignments:
            if a.acknowledged_at and a.assigned_at:
                ttas.append(max(0.0, (_aware(a.acknowledged_at) - _aware(a.assigned_at)).total_seconds() / 60.0))
        return {
            "unacknowledged_incidents": len(unack),
            "escalated_incidents": len(escalated),
            "mtta_minutes": _mean(ttas),
        }
