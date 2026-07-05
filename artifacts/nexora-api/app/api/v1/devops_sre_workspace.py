"""DevOps & SRE workspace REST API (Sprint 63C)."""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from fastapi.responses import Response as FastAPIResponse

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.devops_sre_workspace import (
    AIContextRequest,
    AIContextView,
    AutomationSuggestionView,
    BriefingView,
    CalendarEventView,
    ChangeCenterView,
    CostOperationsView,
    ExecutiveView,
    HandoverView,
    MaintenanceCenterView,
    MaintenanceCreate,
    MaintenanceView,
    MyWorkDashboardView,
    OperationalKPIsView,
    OperationsQueueView,
    QueueItemView,
    SLOCenterView,
)
from app.services.devops_sre_workspace import DevOpsSREWorkspaceService

router = APIRouter(prefix="/ops-workspace", tags=["Ops Workspace"])


def _svc(session) -> DevOpsSREWorkspaceService:
    return DevOpsSREWorkspaceService(session)


@router.get("/my-work", response_model=MyWorkDashboardView)
async def my_work(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).my_work(current_user, org_context)
    await session.commit()
    return MyWorkDashboardView(**data)


@router.get("/queue", response_model=OperationsQueueView)
async def operations_queue(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).queue(current_user, org_context)
    await session.commit()
    return OperationsQueueView(
        items=[QueueItemView(**i) for i in data["items"]],
        total=data["total"],
    )


@router.get("/changes", response_model=ChangeCenterView)
async def change_center(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).changes(current_user, org_context)
    await session.commit()
    return ChangeCenterView(**data)


@router.get("/maintenance", response_model=MaintenanceCenterView)
async def maintenance_center(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).list_maintenance(current_user, org_context)
    await session.commit()
    return MaintenanceCenterView(
        windows=[MaintenanceView.model_validate(w) for w in data["windows"]],
        upcoming=[MaintenanceView.model_validate(w) for w in data["upcoming"]],
        active_freezes=[MaintenanceView.model_validate(w) for w in data["active_freezes"]],
    )


@router.post("/maintenance", response_model=MaintenanceView, status_code=status.HTTP_201_CREATED)
async def create_maintenance(
    payload: MaintenanceCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).create_maintenance(current_user, org_context, payload)
    await session.commit()
    return MaintenanceView.model_validate(row)


@router.post("/maintenance/{window_id}/decide", response_model=MaintenanceView)
async def decide_maintenance(
    window_id: str,
    approved: bool = Query(...),
    current_user: CurrentUser = ...,
    session: DBSession = ...,
    org_context: OrgContextDep = ...,
):
    row = await _svc(session).approve_maintenance(current_user, org_context, window_id, approved=approved)
    await session.commit()
    return MaintenanceView.model_validate(row)


@router.get("/calendar", response_model=list[CalendarEventView])
async def operations_calendar(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).calendar_events(current_user, org_context)
    await session.commit()
    return [CalendarEventView.model_validate(r) for r in rows]


@router.get("/slo", response_model=SLOCenterView)
async def slo_center(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).slo_center(current_user, org_context)
    await session.commit()
    return SLOCenterView(**data)


@router.get("/cost", response_model=CostOperationsView)
async def cost_operations(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).cost_operations(current_user, org_context)
    await session.commit()
    return CostOperationsView(**data)


@router.get("/executive", response_model=ExecutiveView)
async def executive_view(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).executive(current_user, org_context)
    await session.commit()
    return ExecutiveView(**data)


@router.get("/executive/export/pdf")
async def executive_pdf(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    pdf = await _svc(session).executive_pdf(current_user, org_context)
    await session.commit()
    return FastAPIResponse(content=pdf, media_type="application/pdf")


@router.post("/briefing/daily", response_model=BriefingView, status_code=status.HTTP_201_CREATED)
async def generate_daily_briefing(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    row = await _svc(session).generate_daily_briefing(current_user, org_context)
    await session.commit()
    return BriefingView.model_validate(row)


@router.get("/briefing/daily/latest", response_model=BriefingView | None)
async def latest_daily_briefing(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    row = await _svc(session).latest_briefing(current_user, org_context)
    await session.commit()
    return BriefingView.model_validate(row) if row else None


@router.post("/handover", response_model=HandoverView, status_code=status.HTTP_201_CREATED)
async def generate_handover(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    row = await _svc(session).generate_handover(current_user, org_context)
    await session.commit()
    return HandoverView.model_validate(row)


@router.get("/handover/latest", response_model=HandoverView | None)
async def latest_handover(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    row = await _svc(session).latest_handover(current_user, org_context)
    await session.commit()
    return HandoverView.model_validate(row) if row else None


@router.get("/handover/{handover_id}/export/pdf")
async def handover_pdf(
    handover_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    pdf = await _svc(session).handover_pdf(current_user, org_context, handover_id)
    await session.commit()
    return FastAPIResponse(content=pdf, media_type="application/pdf")


@router.get("/search")
async def unified_search(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=100),
):
    data = await _svc(session).unified_search(current_user, org_context, query=q, limit=limit)
    await session.commit()
    return data


@router.get("/kpis", response_model=OperationalKPIsView)
async def operational_kpis(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
    window_days: int = Query(30, ge=7, le=90),
):
    data = await _svc(session).kpis(current_user, org_context, window_days=window_days)
    await session.commit()
    return OperationalKPIsView(**data)


@router.get("/automation-suggestions", response_model=list[AutomationSuggestionView])
async def automation_suggestions(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).automation_suggestions(current_user, org_context)
    await session.commit()
    return [AutomationSuggestionView.model_validate(r) for r in rows]


@router.post("/automation-suggestions/{suggestion_id}/dismiss", response_model=AutomationSuggestionView)
async def dismiss_automation(
    suggestion_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).dismiss_automation(current_user, org_context, suggestion_id)
    await session.commit()
    return AutomationSuggestionView.model_validate(row)


@router.post("/ai-context", response_model=AIContextView)
async def ai_context(
    payload: AIContextRequest, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    data = await _svc(session).ai_context(
        current_user, org_context,
        page=payload.page, reference_type=payload.reference_type,
        reference_id=payload.reference_id, question=payload.question,
    )
    await session.commit()
    return AIContextView(**data)
