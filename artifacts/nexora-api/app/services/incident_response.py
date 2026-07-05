"""Enterprise Incident Response & On-Call Platform orchestration (Sprint 65C).

Extends on-call, escalation, lifecycle, war room, postmortem, SRE commander,
observability correlation — does not duplicate engines.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.org_context import OrgContext
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.incident_response.analytics import compute_analytics
from app.incident_response.communications import DEFAULT_TEMPLATES, render_template
from app.incident_response.coordinator import coordinate_incident
from app.incident_response.status_page import build_public_view
from app.incident_response.types import ESCALATION_CHANNELS
from app.models.incident_response import (
    IrCommunication,
    IrCommunicationTemplate,
    IrCoordinatorRun,
    IrMajorIncident,
    IrScheduleOverride,
    IrStatusComponent,
    IrStatusIncident,
    IrStatusPage,
    IrStatusSubscriber,
)
from app.models.user import User
from app.platform.events import DomainEventType, emit_event
from app.repositories.audit import AuditLogRepository
from app.repositories.incident import IncidentInvestigationRepository, MonitoringAlertRepository
from app.repositories.incident_response import (
    IrCommunicationRepo,
    IrCommunicationTemplateRepo,
    IrCoordinatorRunRepo,
    IrMajorIncidentRepo,
    IrScheduleOverrideRepo,
    IrStatusComponentRepo,
    IrStatusIncidentRepo,
    IrStatusPageRepo,
    IrStatusSubscriberRepo,
)
from app.repositories.oncall import EscalationEventRepository, IncidentAssignmentRepository
from app.repositories.postmortem import PostmortemRepository
from app.schemas.incident_response import (
    CommunicationCreate,
    CommunicationTemplateCreate,
    MajorIncidentCreate,
    ScheduleOverrideCreate,
    StatusComponentCreate,
    StatusIncidentCreate,
    StatusPageCreate,
)
from app.services.incident_lifecycle import IncidentLifecycleService
from app.services.oncall import (
    EscalationEngine,
    OnCallMetricsService,
    OnCallService,
    resolve_current_oncall,
)
from app.services.postmortem import PostmortemService
from app.services.war_room import WarRoomService
from app.tenancy.permissions import can_read_resources, can_write_resources

logger = get_logger(__name__)


class IncidentResponsePlatformService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.overrides = IrScheduleOverrideRepo(session)
        self.status_pages = IrStatusPageRepo(session)
        self.components = IrStatusComponentRepo(session)
        self.status_incidents = IrStatusIncidentRepo(session)
        self.subscribers = IrStatusSubscriberRepo(session)
        self.templates = IrCommunicationTemplateRepo(session)
        self.communications = IrCommunicationRepo(session)
        self.major = IrMajorIncidentRepo(session)
        self.coordinator_runs = IrCoordinatorRunRepo(session)
        self.incidents = IncidentInvestigationRepository(session)
        self.assignments = IncidentAssignmentRepository(session)
        self.escalation_events = EscalationEventRepository(session)
        self.alerts = MonitoringAlertRepository(session)
        self.postmortems = PostmortemRepository(session)
        self.audit = AuditLogRepository(session)
        self.oncall = OnCallService(session)
        self.escalation = EscalationEngine(session)
        self.metrics = OnCallMetricsService(session)
        self.lifecycle = IncidentLifecycleService(session)
        self.postmortem_svc = PostmortemService(session)
        self.war_room = WarRoomService(session)

    def _ensure_read(self, user: User, org_context: OrgContext) -> str:
        if not can_read_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    def _ensure_write(self, user: User, org_context: OrgContext) -> str:
        if not can_write_resources(org_context.role) and not user.is_superuser:
            raise ForbiddenError("Insufficient permissions")
        return org_context.requires_organization

    def _record_metric(self, name: str, **labels) -> None:
        try:
            from app.observability import metrics
            fn = getattr(metrics, name, None)
            if fn:
                fn(**labels)
        except Exception:  # noqa: BLE001
            pass

    # -------------------------------------------------------------- on-call
    async def oncall_dashboard(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        schedules = await self.oncall.list_schedules(user, org_context)
        current = []
        timeline = []
        now = datetime.now(UTC)
        for s in schedules:
            uid = resolve_current_oncall(s, now)
            override = await self.overrides.active_override(organization_id, s.id, now)
            if override:
                uid = override.replacement_user_id
            current.append({
                "schedule_id": s.id, "schedule_name": s.name,
                "user_id": uid, "rotation_type": s.rotation_type,
                "has_override": override is not None,
            })
            timeline.append({
                "schedule_id": s.id, "anchor_at": str(s.anchor_at),
                "participants": list(s.participants or []),
            })
        all_overrides = []
        for s in schedules[:10]:
            rows = await self.overrides.list_for_schedule(organization_id, s.id)
            all_overrides.extend(rows)
        return {
            "schedules": [
                {"id": s.id, "name": s.name, "team": s.team, "rotation_type": s.rotation_type}
                for s in schedules
            ],
            "current_oncall": current,
            "overrides": [
                {"id": o.id, "schedule_id": o.schedule_id, "replacement_user_id": o.replacement_user_id}
                for o in all_overrides[:20]
            ],
            "shift_timeline": timeline,
        }

    async def create_override(
        self, user: User, org_context: OrgContext, payload: ScheduleOverrideCreate,
    ) -> IrScheduleOverride:
        organization_id = self._ensure_write(user, org_context)
        row = IrScheduleOverride(
            organization_id=organization_id,
            schedule_id=payload.schedule_id,
            replacement_user_id=payload.replacement_user_id,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            reason=payload.reason,
            created_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        await emit_event(
            self.session, DomainEventType.ON_CALL_STARTED,
            organization_id=organization_id,
            payload={"override_id": row.id, "schedule_id": row.schedule_id},
        )
        return row

    # ----------------------------------------------------------- escalation
    async def escalation_dashboard(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        policies = await self.oncall.list_policies(user, org_context)
        events, _ = await self.escalation_events.list_for_org(organization_id, limit=20)
        return {
            "policies": [
                {"id": p.id, "name": p.name, "service_name": p.service_name, "steps": len(steps)}
                for p, steps in policies
            ],
            "recent_events": [
                {"incident_id": e.incident_id, "level": e.level, "target_type": e.target_type}
                for e in events
            ],
            "channels_supported": list(ESCALATION_CHANNELS),
        }

    async def run_escalation(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_write(user, org_context)
        start = time.perf_counter()
        fired = await self.escalation.process_due()
        duration = time.perf_counter() - start
        self._record_metric("record_ir_escalation", duration=duration, count=fired)
        if fired:
            await emit_event(
                self.session, DomainEventType.ESCALATION_TRIGGERED,
                organization_id=organization_id,
                payload={"fired": fired},
            )
            await emit_event(
                self.session, DomainEventType.ESCALATION_SUCCEEDED,
                organization_id=organization_id,
                payload={"fired": fired},
            )
        return {"escalations_fired": fired}

    # ------------------------------------------------------------ status pages
    async def list_status_pages(self, user: User, org_context: OrgContext) -> list[IrStatusPage]:
        organization_id = self._ensure_read(user, org_context)
        return await self.status_pages.list_for_org(organization_id)

    async def create_status_page(
        self, user: User, org_context: OrgContext, payload: StatusPageCreate,
    ) -> IrStatusPage:
        organization_id = self._ensure_write(user, org_context)
        row = IrStatusPage(
            organization_id=organization_id,
            name=payload.name,
            slug=payload.slug,
            visibility=payload.visibility,
            branding=payload.branding,
            created_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_status_page_public(
        self, user: User, org_context: OrgContext, slug: str,
    ) -> dict:
        organization_id = self._ensure_read(user, org_context)
        page = await self.status_pages.get_by_slug(organization_id, slug)
        if not page:
            raise NotFoundError("StatusPage", slug)
        components = await self.components.list_for_page(organization_id, page.id)
        incidents = await self.status_incidents.list_for_page(organization_id, page.id)
        view = build_public_view(
            {"name": page.name, "slug": page.slug, "visibility": page.visibility, "branding": page.branding},
            [{"name": c.name, "status": c.status, "description": c.description} for c in components],
            [{"title": i.title, "status": i.status, "impact": i.impact, "started_at": i.started_at, "updates": i.updates} for i in incidents],
        )
        await emit_event(
            self.session, DomainEventType.STATUS_PAGE_UPDATED,
            organization_id=organization_id,
            payload={"page_id": page.id, "slug": slug},
        )
        self._record_metric("record_ir_status_page_update")
        return view

    async def add_status_component(
        self, user: User, org_context: OrgContext, page_id: str, payload: StatusComponentCreate,
    ) -> IrStatusComponent:
        organization_id = self._ensure_write(user, org_context)
        row = IrStatusComponent(
            organization_id=organization_id,
            page_id=page_id,
            name=payload.name,
            description=payload.description,
            status=payload.status,
            position=payload.position,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def publish_status_incident(
        self, user: User, org_context: OrgContext, page_id: str, payload: StatusIncidentCreate,
    ) -> IrStatusIncident:
        organization_id = self._ensure_write(user, org_context)
        row = IrStatusIncident(
            organization_id=organization_id,
            page_id=page_id,
            incident_id=payload.incident_id,
            title=payload.title,
            impact=payload.impact,
            started_at=datetime.now(UTC),
            updates=[],
        )
        self.session.add(row)
        await self.session.flush()
        await emit_event(
            self.session, DomainEventType.STATUS_PAGE_UPDATED,
            organization_id=organization_id,
            payload={"page_id": page_id, "incident_title": payload.title},
        )
        return row

    # ---------------------------------------------------------- communications
    async def list_templates(self, user: User, org_context: OrgContext) -> list[IrCommunicationTemplate]:
        organization_id = self._ensure_read(user, org_context)
        return await self.templates.list_for_org(organization_id)

    async def create_template(
        self, user: User, org_context: OrgContext, payload: CommunicationTemplateCreate,
    ) -> IrCommunicationTemplate:
        organization_id = self._ensure_write(user, org_context)
        row = IrCommunicationTemplate(
            organization_id=organization_id,
            name=payload.name,
            kind=payload.kind,
            subject=payload.subject,
            body=payload.body,
            locale=payload.locale,
            requires_approval=payload.requires_approval,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def create_communication(
        self, user: User, org_context: OrgContext, payload: CommunicationCreate,
    ) -> IrCommunication:
        organization_id = self._ensure_write(user, org_context)
        if payload.template_key:
            rendered = render_template(payload.template_key, payload.context)
            subject, body, kind = rendered["subject"], rendered["body"], rendered["kind"]
        else:
            subject = payload.subject or "Incident update"
            body = payload.body or ""
            kind = payload.kind
        row = IrCommunication(
            organization_id=organization_id,
            incident_id=payload.incident_id,
            kind=kind,
            subject=subject,
            body=body,
            status="DRAFT",
            scheduled_at=payload.scheduled_at,
            created_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_communications(
        self, user: User, org_context: OrgContext, *, incident_id: str | None = None,
    ) -> list[IrCommunication]:
        organization_id = self._ensure_read(user, org_context)
        return await self.communications.list_for_org(organization_id, incident_id=incident_id)

    @staticmethod
    def builtin_templates() -> dict:
        return DEFAULT_TEMPLATES

    # -------------------------------------------------------- major incidents
    async def start_major_incident(
        self, user: User, org_context: OrgContext, payload: MajorIncidentCreate,
    ) -> IrMajorIncident:
        organization_id = self._ensure_write(user, org_context)
        war_room = await self.war_room.create(
            user, org_context, incident_id=payload.incident_id,
            title=f"Major Incident",
        )
        row = IrMajorIncident(
            organization_id=organization_id,
            incident_id=payload.incident_id,
            war_room_id=getattr(war_room, "id", None),
            roles=payload.roles or {"COMMANDER": user.id},
            stakeholders=payload.stakeholders,
            executive_bridge=payload.executive_bridge,
            status="ACTIVE",
            started_at=datetime.now(UTC),
            created_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        await emit_event(
            self.session, DomainEventType.MAJOR_INCIDENT_STARTED,
            organization_id=organization_id,
            aggregate_type="ir_major_incident",
            aggregate_id=row.id,
            payload={"incident_id": payload.incident_id},
        )
        return row

    async def list_major_incidents(self, user: User, org_context: OrgContext) -> list[IrMajorIncident]:
        organization_id = self._ensure_read(user, org_context)
        return await self.major.list_active(organization_id)

    async def end_major_incident(
        self, user: User, org_context: OrgContext, major_id: str,
    ) -> IrMajorIncident:
        organization_id = self._ensure_write(user, org_context)
        row = await self.major.get_by_id(major_id)
        if not row or row.organization_id != organization_id:
            raise NotFoundError("MajorIncident", major_id)
        row.status = "ENDED"
        row.ended_at = datetime.now(UTC)
        await self.session.flush()
        await emit_event(
            self.session, DomainEventType.MAJOR_INCIDENT_ENDED,
            organization_id=organization_id,
            aggregate_id=row.id,
            payload={"incident_id": row.incident_id},
        )
        return row

    # -------------------------------------------------------- AI coordinator
    async def coordinate(self, user: User, org_context: OrgContext, *, incident_id: str | None = None) -> IrCoordinatorRun:
        organization_id = self._ensure_read(user, org_context)
        inv_rows, _ = await self.incidents.list_for_org(organization_id, limit=20)
        if incident_id:
            inv_rows = [i for i in inv_rows if i.id == incident_id] or inv_rows[:1]
        alert_rows, _ = await self.alerts.list_for_org(organization_id, limit=30)
        dash = await self.oncall_dashboard(user, org_context)
        oncall_users = [{"user_id": c.get("user_id"), "name": c.get("schedule_name")} for c in dash.get("current_oncall", [])]
        result = coordinate_incident(
            incidents=[
                {
                    "id": i.id, "title": i.title, "severity": i.severity,
                    "service": getattr(i, "suspected_provider", None) or "platform",
                    "root_cause": i.root_cause,
                    "created_at": i.created_at,
                }
                for i in inv_rows
            ],
            alerts=[
                {"alert_name": a.alert_name, "severity": a.severity, "service": a.service, "last_seen_at": a.last_seen_at}
                for a in alert_rows
            ],
            oncall_users=oncall_users,
        )
        row = IrCoordinatorRun(
            organization_id=organization_id,
            incident_id=incident_id,
            result=result,
            created_by=user.id,
        )
        self.session.add(row)
        await self.session.flush()
        for responder in result.get("recommended_responders", []):
            if responder.get("user_id") and incident_id:
                await emit_event(
                    self.session, DomainEventType.RESPONDER_ASSIGNED,
                    organization_id=organization_id,
                    payload={"incident_id": incident_id, "user_id": responder["user_id"]},
                )
        return row

    # -------------------------------------------------------------- postmortems
    async def postmortem_dashboard(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        rows, total = await self.postmortem_svc.list(user, org_context, offset=0, limit=50)
        pending = sum(1 for r in rows if (getattr(r, "status", "") or "").upper() != "PUBLISHED")
        completed = total - pending
        return {
            "postmortems": [
                {"id": r.id, "title": r.title, "status": r.status, "incident_id": r.investigation_id}
                for r in rows[:20]
            ],
            "pending_count": pending,
            "completed_count": completed,
        }

    async def generate_postmortem(self, user: User, org_context: OrgContext, incident_id: str):
        row = await self.postmortem_svc.generate(user, org_context, incident_id)
        await emit_event(
            self.session, DomainEventType.POSTMORTEM_GENERATED,
            organization_id=org_context.requires_organization,
            payload={"incident_id": incident_id, "postmortem_id": row.id},
        )
        self._record_metric("record_ir_postmortem_generated")
        return row

    # --------------------------------------------------------------- analytics
    async def analytics(self, user: User, org_context: OrgContext) -> dict:
        organization_id = self._ensure_read(user, org_context)
        mtta_data = await self.metrics.metrics(user, org_context)
        assignments = await self.assignments.list_for_org(organization_id)
        inv_rows, _ = await self.incidents.list_for_org(organization_id, limit=200)
        events, _ = await self.escalation_events.list_for_org(organization_id, limit=100)
        assignment_dicts = []
        for a in assignments[:100]:
            mtta = None
            mttr = None
            if a.acknowledged_at and a.assigned_at:
                mtta = (a.acknowledged_at - a.assigned_at).total_seconds() / 60
            if a.resolved_at and a.assigned_at:
                mttr = (a.resolved_at - a.assigned_at).total_seconds() / 60
            assignment_dicts.append({
                "responder_id": a.responder_id, "owner_id": a.owner_id,
                "mtta_minutes": mtta, "mttr_minutes": mttr,
                "acknowledged_at": a.acknowledged_at,
            })
        data = compute_analytics(
            assignments=assignment_dicts,
            incidents=[
                {
                    "severity": i.severity,
                    "service_name": getattr(i, "suspected_provider", None),
                    "lifecycle_status": i.lifecycle_status,
                    "root_cause": i.root_cause, "created_at": i.created_at,
                }
                for i in inv_rows
            ],
            escalations=[{"level": e.level} for e in events],
        )
        data["mtta_minutes"] = data.get("mtta_minutes") or mtta_data.get("organization_mtta_minutes")
        data["mttr_minutes"] = data.get("mttr_minutes") or mtta_data.get("organization_mttr_minutes")
        try:
            from app.observability import metrics
            metrics.set_ir_incident_metrics(
                open_count=data.get("open_incidents", 0),
                mtta=data.get("mtta_minutes"),
                mttr=data.get("mttr_minutes"),
                oncall_coverage=len(await self.oncall.list_schedules(user, org_context)),
            )
        except Exception:  # noqa: BLE001
            pass
        self._record_metric("record_ir_analytics_query")
        return data
