"""Sprint 58A.4 — Complete Incident Lifecycle service.

Turns the incident into a real, validated, end-to-end workflow and the incident
detail into a command center. It orchestrates EXISTING engines (investigation,
on-call routing/escalation, war room, postmortem, remediation) — it adds the
lifecycle state machine, human collaboration (comments/tasks), assignment, and
the unified aggregate view. Every action is recorded as an
``IncidentLifecycleEvent`` and audit-logged. Read-only w.r.t. infrastructure;
remediation stays human-approved.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NexoraException
from app.models.incident import IncidentLifecycleStatus
from app.models.incident_lifecycle import (
    IncidentLifecycleEventType,
    IncidentTaskStatus,
)
from app.models.oncall import IncidentAssignmentState
from app.models.user import User
from app.repositories.audit import AuditLogRepository
from app.repositories.incident import (
    DeploymentChangeEventRepository,
    IncidentInvestigationRepository,
    IncidentInvestigationStepRepository,
    IncidentRecommendationRepository,
    IncidentRemediationActionRepository,
    IncidentTimelineEventRepository,
)
from app.repositories.incident_lifecycle import (
    IncidentCommentRepository,
    IncidentLifecycleEventRepository,
    IncidentTaskRepository,
)
from app.repositories.oncall import IncidentAssignmentRepository
from app.repositories.postmortem import PostmortemRepository
from app.repositories.war_room import WarRoomRepository
from app.schemas.incident import (
    DeploymentChangeEventResponse,
    IncidentRecommendationResponse,
    IncidentResponse,
    IncidentStepResponse,
    IncidentTimelineEventResponse,
    RemediationActionResponse,
)
from app.schemas.incident_lifecycle import (
    BusinessImpactView,
    CommandCenterResponse,
    IncidentAssignmentView,
    IncidentCommentResponse,
    IncidentTaskResponse,
    LifecycleEventResponse,
    PostmortemView,
    WarRoomView,
)
from app.services import incident_state_machine as sm
from app.services.incident_notifications import IncidentNotificationService
from app.tenancy.permissions import can_read_ai_teams, can_write_ai_teams

logger = structlog.get_logger(__name__)

_S = IncidentLifecycleStatus


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class IncidentLifecycleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.incident_repo = IncidentInvestigationRepository(session)
        self.event_repo = IncidentLifecycleEventRepository(session)
        self.comment_repo = IncidentCommentRepository(session)
        self.task_repo = IncidentTaskRepository(session)
        self.assignment_repo = IncidentAssignmentRepository(session)
        self.step_repo = IncidentInvestigationStepRepository(session)
        self.timeline_repo = IncidentTimelineEventRepository(session)
        self.change_repo = DeploymentChangeEventRepository(session)
        self.rec_repo = IncidentRecommendationRepository(session)
        self.action_repo = IncidentRemediationActionRepository(session)
        self.war_room_repo = WarRoomRepository(session)
        self.postmortem_repo = PostmortemRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.notifier = IncidentNotificationService(session)

    # --------------------------------------------------------------- guards
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

    async def _get_incident_or_404(self, incident_id: str, organization_id: str):
        incident = await self.incident_repo.get_for_org(incident_id, organization_id)
        if incident is None:
            raise NexoraException("Incident not found.", status_code=404)
        return incident

    async def _record_event(
        self, *, organization_id: str, incident_id: str, event_type: str,
        actor_id: str | None, message: str | None = None,
        from_status: str | None = None, to_status: str | None = None,
        metadata: dict | None = None,
    ):
        return await self.event_repo.create(
            organization_id=organization_id, incident_id=incident_id, event_type=event_type,
            actor_id=actor_id, from_status=from_status, to_status=to_status,
            message=message, event_metadata=metadata or {},
        )

    # --------------------------------------------------------------- transition
    async def transition(
        self, incident_id: str, user: User, org_context: OrgContext, *,
        to_status: str, note: str | None = None,
    ) -> IncidentResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        incident = await self._get_incident_or_404(incident_id, organization_id)

        target = sm.normalize(to_status)
        if not sm.is_valid_state(target):
            raise NexoraException(
                f"Invalid lifecycle status. One of {sorted(sm.VALID_STATES)}.", status_code=400)
        current = sm.normalize(incident.lifecycle_status)
        if target == current:
            raise NexoraException(f"Incident is already {current}.", status_code=409)
        if not sm.can_transition(current, target):
            allowed = sorted(sm.ALLOWED_TRANSITIONS.get(current, set()))
            raise NexoraException(
                f"Cannot transition from {current} to {target}. Allowed: {allowed}.",
                status_code=409)

        await self._apply_transition(incident, target, user, organization_id, note=note)
        await self.audit_repo.log(
            action="incident_lifecycle_transition",
            resource_type="incident_investigation", resource_id=incident.id,
            user_id=user.id,
            details={"organization_id": organization_id, "from": current, "to": target},
        )
        await self.session.commit()
        await self.session.refresh(incident)
        return IncidentResponse.model_validate(incident)

    async def _apply_transition(
        self, incident, target: str, user: User, organization_id: str, *, note: str | None,
    ) -> None:
        """Mutate the incident + side effects for a (validated) transition."""
        current = sm.normalize(incident.lifecycle_status)
        fields: dict = {"lifecycle_status": target}
        if target == _S.ACKNOWLEDGED.value and incident.acknowledged_at is None:
            fields["acknowledged_at"] = _now()
            fields["acknowledged_by"] = user.id
        if target == _S.RESOLVED.value and incident.resolved_at is None:
            fields["resolved_at"] = _now()
        if target == _S.CLOSED.value and incident.closed_at is None:
            fields["closed_at"] = _now()
        if target == _S.INVESTIGATING.value:
            # Re-open clears terminal timestamps so metrics stay coherent.
            fields["resolved_at"] = None
            fields["closed_at"] = None
        await self.incident_repo.update(incident, **fields)

        await self._record_event(
            organization_id=organization_id, incident_id=incident.id,
            event_type=IncidentLifecycleEventType.STATE_CHANGE.value, actor_id=user.id,
            from_status=current, to_status=target, message=note,
        )

        # Reconcile the on-call assignment state (when one exists).
        assignment_state = sm.assignment_state_for(target)
        if assignment_state:
            assignment = await self.assignment_repo.get_for_incident(incident.id, organization_id)
            if assignment is not None:
                assignment.state = assignment_state
                if assignment_state == IncidentAssignmentState.ACKNOWLEDGED.value and \
                        assignment.acknowledged_at is None:
                    assignment.acknowledged_at = _now()
                    assignment.acknowledged_by_id = user.id
                if assignment_state == IncidentAssignmentState.RESOLVED.value and \
                        assignment.resolved_at is None:
                    assignment.resolved_at = _now()
                await self.session.flush()

        # War room launches automatically when investigation begins.
        if target == _S.INVESTIGATING.value:
            await self._auto_launch_war_room(incident, user, org_context_org=organization_id)

        # Postmortem auto-generates (best-effort, idempotent) on resolve.
        if target == _S.RESOLVED.value:
            try:
                from app.services.postmortem import PostmortemService

                await PostmortemService(self.session).auto_generate_for_incident(
                    organization_id, incident.id, user.id)
                await self._record_event(
                    organization_id=organization_id, incident_id=incident.id,
                    event_type=IncidentLifecycleEventType.POSTMORTEM.value, actor_id=user.id,
                    message="Postmortem auto-generated on resolution.")
            except Exception as exc:  # noqa: BLE001 - never block the resolve flow
                logger.warning("postmortem_autogen_failed", error=type(exc).__name__)

    async def _auto_launch_war_room(self, incident, user: User, *, org_context_org: str) -> None:
        existing = await self.war_room_repo.get_for_incident(incident.id, org_context_org)
        if existing is not None:
            return
        try:
            room = await self.war_room_repo.create(
                organization_id=org_context_org, incident_id=incident.id,
                title=f"War Room: {incident.title}"[:255],
                status="OPEN", requires_approval=True, created_by=user.id,
            )
            await self._record_event(
                organization_id=org_context_org, incident_id=incident.id,
                event_type=IncidentLifecycleEventType.WAR_ROOM.value, actor_id=user.id,
                message="War room launched automatically.",
                metadata={"war_room_id": room.id})
        except Exception as exc:  # noqa: BLE001 - best effort
            logger.warning("war_room_autolaunch_failed", error=type(exc).__name__)

    # --------------------------------------------------------------- acknowledge
    async def acknowledge(
        self, incident_id: str, user: User, org_context: OrgContext, *, note: str | None = None
    ) -> IncidentResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        incident = await self._get_incident_or_404(incident_id, organization_id)
        current = sm.normalize(incident.lifecycle_status)
        if current in (_S.RESOLVED.value, _S.CLOSED.value):
            raise NexoraException(f"Cannot acknowledge a {current} incident.", status_code=409)
        if current == _S.OPEN.value:
            await self._apply_transition(incident, _S.ACKNOWLEDGED.value, user, organization_id, note=note)
        else:
            # Already past OPEN — just stamp acknowledgement metadata.
            if incident.acknowledged_at is None:
                await self.incident_repo.update(
                    incident, acknowledged_at=_now(), acknowledged_by=user.id)
        await self.audit_repo.log(
            action="incident_acknowledged", resource_type="incident_investigation",
            resource_id=incident.id, user_id=user.id,
            details={"organization_id": organization_id})
        await self.session.commit()
        await self.session.refresh(incident)
        return IncidentResponse.model_validate(incident)

    # --------------------------------------------------------------- assignment
    async def assign(
        self, incident_id: str, user: User, org_context: OrgContext, *,
        assignee_id: str, note: str | None = None,
    ) -> IncidentResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        incident = await self._get_incident_or_404(incident_id, organization_id)
        previous = incident.assignee_id
        await self.incident_repo.update(incident, assignee_id=assignee_id)

        # Keep the on-call assignment's responder in sync when present.
        assignment = await self.assignment_repo.get_for_incident(incident.id, organization_id)
        if assignment is not None:
            assignment.responder_id = assignee_id
            await self.session.flush()

        verb = "reassigned" if previous else "assigned"
        await self._record_event(
            organization_id=organization_id, incident_id=incident.id,
            event_type=IncidentLifecycleEventType.ASSIGNMENT.value, actor_id=user.id,
            message=note or f"Incident {verb} to {assignee_id}.",
            metadata={"assignee_id": assignee_id, "previous_assignee_id": previous})
        # Page the new assignee (best-effort, customer-safe).
        try:
            await self.notifier.notify_recipient(
                organization_id=organization_id, incident_id=incident.id,
                title=incident.title, severity=incident.severity or "HIGH",
                reason=f"incident {verb}", recipient_user_id=assignee_id,
                recipient_label="assignee", user_id=user.id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("assignment_notify_failed", error=type(exc).__name__)
        await self.audit_repo.log(
            action="incident_assignee_set", resource_type="incident_investigation",
            resource_id=incident.id, user_id=user.id,
            details={"organization_id": organization_id, "assignee_id": assignee_id,
                     "previous_assignee_id": previous})
        await self.session.commit()
        await self.session.refresh(incident)
        return IncidentResponse.model_validate(incident)

    # --------------------------------------------------------------- escalate
    async def escalate(
        self, incident_id: str, user: User, org_context: OrgContext, *,
        reason: str | None = None, run_escalation: bool = False,
    ) -> IncidentResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        incident = await self._get_incident_or_404(incident_id, organization_id)
        current = sm.normalize(incident.lifecycle_status)
        if current != _S.ESCALATED.value and sm.can_transition(current, _S.ESCALATED.value):
            await self._apply_transition(incident, _S.ESCALATED.value, user, organization_id, note=reason)
        await self._record_event(
            organization_id=organization_id, incident_id=incident.id,
            event_type=IncidentLifecycleEventType.ESCALATION.value, actor_id=user.id,
            message=reason or "Incident manually escalated.")
        await self.audit_repo.log(
            action="incident_escalated_manual", resource_type="incident_investigation",
            resource_id=incident.id, user_id=user.id,
            details={"organization_id": organization_id})
        await self.session.commit()
        # Optionally advance the on-call escalation ladder immediately.
        if run_escalation:
            try:
                from app.services.oncall import EscalationEngine

                await EscalationEngine(self.session).process_due()
            except Exception as exc:  # noqa: BLE001
                logger.warning("escalation_run_failed", error=type(exc).__name__)
        await self.session.refresh(incident)
        return IncidentResponse.model_validate(incident)

    # --------------------------------------------------------------- comments
    async def add_comment(
        self, incident_id: str, user: User, org_context: OrgContext, *, body: str
    ) -> IncidentCommentResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        incident = await self._get_incident_or_404(incident_id, organization_id)
        comment = await self.comment_repo.create(
            organization_id=organization_id, incident_id=incident.id,
            author_id=user.id, body=body)
        await self._record_event(
            organization_id=organization_id, incident_id=incident.id,
            event_type=IncidentLifecycleEventType.COMMENT.value, actor_id=user.id,
            message=body[:500])
        await self.audit_repo.log(
            action="incident_comment_added", resource_type="incident_comment",
            resource_id=comment.id, user_id=user.id,
            details={"organization_id": organization_id, "incident_id": incident.id})
        await self.session.commit()
        return IncidentCommentResponse.model_validate(comment)

    async def list_comments(
        self, incident_id: str, user: User, org_context: OrgContext
    ) -> list[IncidentCommentResponse]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        await self._get_incident_or_404(incident_id, organization_id)
        rows = await self.comment_repo.list_for_incident(incident_id, organization_id)
        return [IncidentCommentResponse.model_validate(r) for r in rows]

    # --------------------------------------------------------------- tasks
    async def create_task(
        self, incident_id: str, user: User, org_context: OrgContext, *,
        title: str, description: str | None = None, assignee_id: str | None = None,
    ) -> IncidentTaskResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        incident = await self._get_incident_or_404(incident_id, organization_id)
        task = await self.task_repo.create(
            organization_id=organization_id, incident_id=incident.id, title=title,
            description=description, assignee_id=assignee_id, created_by=user.id,
            status=IncidentTaskStatus.TODO.value)
        await self._record_event(
            organization_id=organization_id, incident_id=incident.id,
            event_type=IncidentLifecycleEventType.TASK.value, actor_id=user.id,
            message=f"Task created: {title}"[:500], metadata={"task_id": task.id})
        await self.audit_repo.log(
            action="incident_task_created", resource_type="incident_task",
            resource_id=task.id, user_id=user.id,
            details={"organization_id": organization_id, "incident_id": incident.id})
        await self.session.commit()
        return IncidentTaskResponse.model_validate(task)

    async def update_task(
        self, incident_id: str, task_id: str, user: User, org_context: OrgContext, *,
        title: str | None = None, description: str | None = None,
        status: str | None = None, assignee_id: str | None = None,
    ) -> IncidentTaskResponse:
        organization_id = org_context.requires_organization
        self._ensure_write(user, org_context)
        task = await self.task_repo.get_for_org(task_id, organization_id)
        if task is None or task.incident_id != incident_id:
            raise NexoraException("Task not found.", status_code=404)
        fields: dict = {}
        if title is not None:
            fields["title"] = title
        if description is not None:
            fields["description"] = description
        if assignee_id is not None:
            fields["assignee_id"] = assignee_id
        if status is not None:
            st = status.strip().upper()
            valid = {s.value for s in IncidentTaskStatus}
            if st not in valid:
                raise NexoraException(f"Invalid task status. One of {sorted(valid)}.", status_code=400)
            fields["status"] = st
            fields["completed_at"] = _now() if st == IncidentTaskStatus.DONE.value else None
        if fields:
            await self.task_repo.update(task, **fields)
        await self.audit_repo.log(
            action="incident_task_updated", resource_type="incident_task",
            resource_id=task.id, user_id=user.id,
            details={"organization_id": organization_id, "status": task.status})
        await self.session.commit()
        await self.session.refresh(task)
        return IncidentTaskResponse.model_validate(task)

    async def list_tasks(
        self, incident_id: str, user: User, org_context: OrgContext
    ) -> list[IncidentTaskResponse]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        await self._get_incident_or_404(incident_id, organization_id)
        rows = await self.task_repo.list_for_incident(incident_id, organization_id)
        return [IncidentTaskResponse.model_validate(r) for r in rows]

    # --------------------------------------------------------------- events
    async def list_events(
        self, incident_id: str, user: User, org_context: OrgContext
    ) -> list[LifecycleEventResponse]:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        await self._get_incident_or_404(incident_id, organization_id)
        rows = await self.event_repo.list_for_incident(incident_id, organization_id)
        return [LifecycleEventResponse.model_validate(r) for r in rows]

    # --------------------------------------------------------------- command center
    async def command_center(
        self, incident_id: str, user: User, org_context: OrgContext
    ) -> CommandCenterResponse:
        organization_id = org_context.requires_organization
        self._ensure_read(user, org_context)
        incident = await self._get_incident_or_404(incident_id, organization_id)

        steps = await self.step_repo.list_for_investigation(incident.id, organization_id)
        timeline = await self.timeline_repo.list_for_investigation(incident.id, organization_id)
        changes = await self.change_repo.list_for_investigation(incident.id, organization_id)
        recs = await self.rec_repo.list_for_investigation(incident.id, organization_id)
        actions = await self.action_repo.list_for_investigation(incident.id, organization_id)
        comments = await self.comment_repo.list_for_incident(incident.id, organization_id)
        tasks = await self.task_repo.list_for_incident(incident.id, organization_id)
        events = await self.event_repo.list_for_incident(incident.id, organization_id)
        assignment = await self.assignment_repo.get_for_incident(incident.id, organization_id)
        war_room = await self.war_room_repo.get_for_incident(incident.id, organization_id)
        postmortem = await self.postmortem_repo.get_for_investigation(incident.id, organization_id)

        current = sm.normalize(incident.lifecycle_status)
        available = sorted(sm.ALLOWED_TRANSITIONS.get(current, set()))

        ai_findings: list[str] = []
        if incident.root_cause:
            ai_findings.append(f"Root cause: {incident.root_cause}")
        if incident.suspected_trigger:
            ai_findings.append(f"Suspected trigger: {incident.suspected_trigger}")
        if war_room is not None and war_room.consensus_rca:
            ai_findings.append(f"War room consensus: {war_room.consensus_rca}")
        for r in recs[:5]:
            ai_findings.append(f"Recommendation: {r.title}")

        assignment_view = None
        if assignment is not None:
            assignment_view = IncidentAssignmentView(
                state=assignment.state, service_name=assignment.service_name,
                owner_id=assignment.owner_id, responder_id=assignment.responder_id,
                approver_id=assignment.approver_id, current_level=assignment.current_level,
                acknowledged_at=assignment.acknowledged_at, resolved_at=assignment.resolved_at)

        war_room_view = None
        if war_room is not None:
            war_room_view = WarRoomView(
                id=war_room.id, status=war_room.status, title=war_room.title,
                confidence_score=war_room.confidence_score,
                message_count=war_room.message_count or 0)

        postmortem_view = None
        if postmortem is not None:
            postmortem_view = PostmortemView(
                id=postmortem.id, status=postmortem.status, title=postmortem.title,
                version=postmortem.version or 1, generated_by=postmortem.generated_by)

        # Business impact (cheap, customer-safe estimate).
        opened = _aware(incident.created_at)
        end = _aware(incident.resolved_at) or _now()
        open_minutes = int((end - opened).total_seconds() / 60) if opened else None
        sev = (incident.severity or "").upper()
        business_impact = BusinessImpactView(
            severity=incident.severity,
            affected_service=assignment.service_name if assignment else None,
            blast_radius=0,
            open_minutes=open_minutes,
            customer_facing=sev in ("CRITICAL", "HIGH"))

        return CommandCenterResponse(
            incident=IncidentResponse.model_validate(incident),
            available_transitions=available,
            assignment=assignment_view,
            lifecycle_events=[LifecycleEventResponse.model_validate(e) for e in events],
            ai_findings=ai_findings,
            timeline=[IncidentTimelineEventResponse.model_validate(t) for t in timeline],
            related_changes=[DeploymentChangeEventResponse.model_validate(c) for c in changes],
            recommendations=[IncidentRecommendationResponse.model_validate(r) for r in recs],
            remediation_actions=[RemediationActionResponse.model_validate(a) for a in actions],
            comments=[IncidentCommentResponse.model_validate(c) for c in comments],
            tasks=[IncidentTaskResponse.model_validate(t) for t in tasks],
            steps=[IncidentStepResponse.model_validate(s) for s in steps],
            war_room=war_room_view,
            postmortem=postmortem_view,
            business_impact=business_impact,
        )
