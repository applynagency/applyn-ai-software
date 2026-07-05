"""Enterprise Incident Response & On-Call Platform REST API (Sprint 65C).

Mounted under /v1/incidents/* — static routes registered before /{id} paths.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.incident_response import (
    AnalyticsView,
    CommunicationCreate,
    CommunicationTemplateCreate,
    CommunicationView,
    CoordinatorRequest,
    EscalationDashboardView,
    MajorIncidentCreate,
    MajorIncidentView,
    OncallDashboardView,
    PostmortemPlatformView,
    ScheduleOverrideCreate,
    ScheduleOverrideView,
    StatusComponentCreate,
    StatusComponentView,
    StatusIncidentCreate,
    StatusPageCreate,
    StatusPageView,
)
from app.services.incident_response import IncidentResponsePlatformService

router = APIRouter(prefix="/incidents", tags=["Incident Response Platform"])


def _svc(session) -> IncidentResponsePlatformService:
    return IncidentResponsePlatformService(session)


# ------------------------------------------------------------------ on-call
@router.get("/oncall", response_model=OncallDashboardView)
async def oncall_dashboard(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).oncall_dashboard(current_user, org_context)
    await session.commit()
    return OncallDashboardView(**data)


@router.post("/oncall/overrides", response_model=ScheduleOverrideView, status_code=status.HTTP_201_CREATED)
async def create_schedule_override(
    payload: ScheduleOverrideCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    row = await _svc(session).create_override(current_user, org_context, payload)
    await session.commit()
    return ScheduleOverrideView.model_validate(row)


# --------------------------------------------------------------- escalation
@router.get("/escalation", response_model=EscalationDashboardView)
async def escalation_dashboard(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).escalation_dashboard(current_user, org_context)
    await session.commit()
    return EscalationDashboardView(**data)


@router.post("/escalation/run")
async def run_escalation(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).run_escalation(current_user, org_context)
    await session.commit()
    return data


# ------------------------------------------------------------- status pages
@router.get("/status-pages", response_model=list[StatusPageView])
async def list_status_pages(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_status_pages(current_user, org_context)
    await session.commit()
    return [StatusPageView.model_validate(r) for r in rows]


@router.post("/status-pages", response_model=StatusPageView, status_code=status.HTTP_201_CREATED)
async def create_status_page(
    payload: StatusPageCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    row = await _svc(session).create_status_page(current_user, org_context, payload)
    await session.commit()
    return StatusPageView.model_validate(row)


@router.get("/status-pages/{slug}/public")
async def public_status_page(
    slug: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    data = await _svc(session).get_status_page_public(current_user, org_context, slug)
    await session.commit()
    return data


@router.post(
    "/status-pages/{page_id}/components",
    response_model=StatusComponentView,
    status_code=status.HTTP_201_CREATED,
)
async def add_status_component(
    page_id: str,
    payload: StatusComponentCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    row = await _svc(session).add_status_component(current_user, org_context, page_id, payload)
    await session.commit()
    return StatusComponentView.model_validate(row)


@router.post("/status-pages/{page_id}/incidents", status_code=status.HTTP_201_CREATED)
async def publish_status_incident(
    page_id: str,
    payload: StatusIncidentCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    row = await _svc(session).publish_status_incident(current_user, org_context, page_id, payload)
    await session.commit()
    return {"id": row.id, "title": row.title, "status": row.status}


# ---------------------------------------------------------- communications
@router.get("/communications/templates")
async def list_communication_templates(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    builtin = IncidentResponsePlatformService.builtin_templates()
    custom = await _svc(session).list_templates(current_user, org_context)
    await session.commit()
    return {"builtin": builtin, "custom": [{"id": t.id, "name": t.name, "kind": t.kind} for t in custom]}


@router.post("/communications/templates", status_code=status.HTTP_201_CREATED)
async def create_communication_template(
    payload: CommunicationTemplateCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    row = await _svc(session).create_template(current_user, org_context, payload)
    await session.commit()
    return {"id": row.id, "name": row.name}


@router.get("/communications", response_model=list[CommunicationView])
async def list_communications(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    incident_id: str | None = None,
):
    rows = await _svc(session).list_communications(current_user, org_context, incident_id=incident_id)
    await session.commit()
    return [CommunicationView.model_validate(r) for r in rows]


@router.post("/communications", response_model=CommunicationView, status_code=status.HTTP_201_CREATED)
async def create_communication(
    payload: CommunicationCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    row = await _svc(session).create_communication(current_user, org_context, payload)
    await session.commit()
    return CommunicationView.model_validate(row)


# --------------------------------------------------------------- postmortems
@router.get("/postmortems", response_model=PostmortemPlatformView)
async def postmortem_dashboard(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).postmortem_dashboard(current_user, org_context)
    await session.commit()
    return PostmortemPlatformView(**data)


@router.post("/postmortems/{incident_id}/generate", status_code=status.HTTP_201_CREATED)
async def generate_postmortem(
    incident_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).generate_postmortem(current_user, org_context, incident_id)
    await session.commit()
    return {"id": row.id, "title": row.title, "status": row.status}


# ------------------------------------------------------------------ analytics
@router.get("/analytics", response_model=AnalyticsView)
async def incident_analytics(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).analytics(current_user, org_context)
    await session.commit()
    return AnalyticsView(**data)


# -------------------------------------------------------- major + coordinator
@router.get("/major", response_model=list[MajorIncidentView])
async def list_major_incidents(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_major_incidents(current_user, org_context)
    await session.commit()
    return [MajorIncidentView.model_validate(r) for r in rows]


@router.post("/major", response_model=MajorIncidentView, status_code=status.HTTP_201_CREATED)
async def start_major_incident(
    payload: MajorIncidentCreate,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    row = await _svc(session).start_major_incident(current_user, org_context, payload)
    await session.commit()
    return MajorIncidentView.model_validate(row)


@router.post("/major/{major_id}/end", response_model=MajorIncidentView)
async def end_major_incident(
    major_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).end_major_incident(current_user, org_context, major_id)
    await session.commit()
    return MajorIncidentView.model_validate(row)


@router.post("/coordinate", status_code=status.HTTP_201_CREATED)
async def coordinate_incident(
    payload: CoordinatorRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    row = await _svc(session).coordinate(current_user, org_context, incident_id=payload.incident_id)
    await session.commit()
    return {"id": row.id, "result": row.result}
