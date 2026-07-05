"""Product excellence API (Sprint 63A).

* ``/v1/product/inbox``           — notification center (read/unread/pin/snooze)
* ``/v1/product/timeline/{type}/{id}`` — universal resource timeline
* ``/v1/product/views``           — saved views (filters/searches/layouts)
* ``/v1/product/dashboards``      — drag-and-drop dashboard builder
* ``/v1/product/reports/schedules`` — scheduled report delivery
* ``/v1/product/collaboration``   — comments + reactions
* ``/v1/product/preferences``     — user personalization
* ``/v1/product/analytics``       — product analytics (privacy-aware)
* ``/v1/product/commands``        — universal command palette
* ``/v1/product/docs/diagrams``   — auto-generated architecture diagrams
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.auth.dependencies import DBSession
from app.auth.org_context import OrgContext, OrgContextDep
from app.models.organization import OrganizationRole
from app.platform.product import (
    CollaborationService,
    CommandPaletteService,
    DashboardService,
    InboxService,
    PersonalizationService,
    ProductAnalyticsService,
    ReportScheduleService,
    SavedViewService,
    TimelineService,
)
from app.schemas.product import (
    AnalyticsTrackRequest,
    CommandPaletteResponse,
    CommentRequest,
    CommentResponse,
    DashboardRequest,
    DashboardResponse,
    InboxNotificationResponse,
    PreferenceRequest,
    ReactionRequest,
    ReportScheduleRequest,
    ReportScheduleResponse,
    SavedViewRequest,
    SavedViewResponse,
    TimelineResponse,
)

router = APIRouter(prefix="/product", tags=["Product"])

_ADMIN_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN}


def _org(ctx: OrgContext) -> str:
    return ctx.requires_organization


# --------------------------------------------------------------------------- #
# Inbox notification center
# --------------------------------------------------------------------------- #
@router.get("/inbox", response_model=list[InboxNotificationResponse])
async def list_inbox(
    session: DBSession, ctx: OrgContextDep,
    unread_only: bool = False, category: str | None = None,
    pinned_only: bool = False, limit: int = Query(50, le=200), offset: int = 0,
):
    org_id = _org(ctx)
    return await InboxService(session).list_inbox(
        organization_id=org_id, user_id=ctx.user.id,
        unread_only=unread_only, category=category, pinned_only=pinned_only,
        limit=limit, offset=offset)


@router.get("/inbox/unread-count")
async def inbox_unread_count(session: DBSession, ctx: OrgContextDep):
    org_id = _org(ctx)
    count = await InboxService(session).unread_count(
        organization_id=org_id, user_id=ctx.user.id)
    return {"unread": count}


@router.post("/inbox/{note_id}/read", response_model=InboxNotificationResponse)
async def mark_inbox_read(note_id: str, session: DBSession, ctx: OrgContextDep):
    note = await InboxService(session).mark_read(note_id, user_id=ctx.user.id)
    if note is None:
        raise HTTPException(status_code=404, detail="notification not found")
    await session.commit()
    return note


@router.post("/inbox/read-all")
async def mark_all_inbox_read(session: DBSession, ctx: OrgContextDep):
    org_id = _org(ctx)
    count = await InboxService(session).mark_all_read(
        organization_id=org_id, user_id=ctx.user.id)
    await session.commit()
    return {"marked": count}


@router.post("/inbox/{note_id}/pin", response_model=InboxNotificationResponse)
async def pin_inbox(note_id: str, session: DBSession, ctx: OrgContextDep,
                    pinned: bool = Query(True)):
    note = await InboxService(session).pin(note_id, user_id=ctx.user.id, pinned=pinned)
    if note is None:
        raise HTTPException(status_code=404, detail="notification not found")
    await session.commit()
    return note


@router.post("/inbox/{note_id}/snooze", response_model=InboxNotificationResponse)
async def snooze_inbox(note_id: str, session: DBSession, ctx: OrgContextDep,
                       minutes: int = Query(60, ge=1, le=10080)):
    note = await InboxService(session).snooze(note_id, user_id=ctx.user.id, minutes=minutes)
    if note is None:
        raise HTTPException(status_code=404, detail="notification not found")
    await session.commit()
    return note


# --------------------------------------------------------------------------- #
# Universal timeline
# --------------------------------------------------------------------------- #
@router.get("/timeline/{resource_type}/{resource_id}", response_model=TimelineResponse)
async def resource_timeline(
    resource_type: str, resource_id: str,
    session: DBSession, ctx: OrgContextDep, limit: int = Query(100, le=500),
):
    org_id = _org(ctx)
    items = await TimelineService(session).get(
        organization_id=org_id, resource_type=resource_type,
        resource_id=resource_id, limit=limit)
    return TimelineResponse(resource_type=resource_type, resource_id=resource_id, items=items)


# --------------------------------------------------------------------------- #
# Saved views
# --------------------------------------------------------------------------- #
@router.get("/views", response_model=list[SavedViewResponse])
async def list_saved_views(session: DBSession, ctx: OrgContextDep,
                           view_type: str | None = None):
    org_id = _org(ctx)
    return await SavedViewService(session).list(
        organization_id=org_id, user_id=ctx.user.id, view_type=view_type)


@router.post("/views", response_model=SavedViewResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_view(body: SavedViewRequest, session: DBSession, ctx: OrgContextDep):
    org_id = _org(ctx)
    view = await SavedViewService(session).create(
        organization_id=org_id, user_id=ctx.user.id, **body.model_dump())
    await session.commit()
    return view


@router.delete("/views/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_view(view_id: str, session: DBSession, ctx: OrgContextDep):
    if not await SavedViewService(session).delete(view_id, user_id=ctx.user.id):
        raise HTTPException(status_code=404, detail="view not found")
    await session.commit()


# --------------------------------------------------------------------------- #
# Dashboard builder
# --------------------------------------------------------------------------- #
@router.get("/dashboards", response_model=list[DashboardResponse])
async def list_dashboards(session: DBSession, ctx: OrgContextDep):
    org_id = _org(ctx)
    return await DashboardService(session).list(organization_id=org_id, user_id=ctx.user.id)


@router.post("/dashboards", response_model=DashboardResponse, status_code=status.HTTP_201_CREATED)
async def create_dashboard(body: DashboardRequest, session: DBSession, ctx: OrgContextDep):
    org_id = _org(ctx)
    dash = await DashboardService(session).create(
        organization_id=org_id, user_id=ctx.user.id, **body.model_dump())
    await session.commit()
    return dash


@router.put("/dashboards/{dash_id}/widgets", response_model=DashboardResponse)
async def update_dashboard_widgets(
    dash_id: str, widgets: list[dict], session: DBSession, ctx: OrgContextDep,
):
    dash = await DashboardService(session).update_widgets(
        dash_id, user_id=ctx.user.id, widgets=widgets)
    if dash is None:
        raise HTTPException(status_code=404, detail="dashboard not found")
    await session.commit()
    return dash


@router.delete("/dashboards/{dash_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard(dash_id: str, session: DBSession, ctx: OrgContextDep):
    if not await DashboardService(session).delete(dash_id, user_id=ctx.user.id):
        raise HTTPException(status_code=404, detail="dashboard not found")
    await session.commit()


# --------------------------------------------------------------------------- #
# Report schedules
# --------------------------------------------------------------------------- #
@router.get("/reports/schedules", response_model=list[ReportScheduleResponse])
async def list_report_schedules(session: DBSession, ctx: OrgContextDep):
    org_id = _org(ctx)
    return await ReportScheduleService(session).list(org_id)


@router.post("/reports/schedules", response_model=ReportScheduleResponse,
             status_code=status.HTTP_201_CREATED)
async def create_report_schedule(body: ReportScheduleRequest, session: DBSession,
                                 ctx: OrgContextDep):
    org_id = _org(ctx)
    sched = await ReportScheduleService(session).create(
        organization_id=org_id, created_by=ctx.user.id, **body.model_dump())
    await session.commit()
    return sched


@router.post("/reports/schedules/run-due")
async def run_due_report_schedules(session: DBSession, ctx: OrgContextDep):
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(status_code=403, detail="Admin required")
    results = await ReportScheduleService(session).run_due()
    await session.commit()
    return {"results": results}


# --------------------------------------------------------------------------- #
# Collaboration
# --------------------------------------------------------------------------- #
@router.get("/collaboration/{resource_type}/{resource_id}/comments",
            response_model=list[CommentResponse])
async def list_comments(resource_type: str, resource_id: str,
                        session: DBSession, ctx: OrgContextDep):
    org_id = _org(ctx)
    return await CollaborationService(session).list_comments(
        organization_id=org_id, resource_type=resource_type, resource_id=resource_id)


@router.post("/collaboration/{resource_type}/{resource_id}/comments",
             response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(resource_type: str, resource_id: str, body: CommentRequest,
                      session: DBSession, ctx: OrgContextDep):
    org_id = _org(ctx)
    comment = await CollaborationService(session).add_comment(
        organization_id=org_id, resource_type=resource_type, resource_id=resource_id,
        author_id=ctx.user.id, body=body.body, parent_id=body.parent_id,
        attachments=body.attachments)
    await session.commit()
    return comment


@router.post("/collaboration/reactions", status_code=status.HTTP_201_CREATED)
async def add_reaction(body: ReactionRequest, session: DBSession, ctx: OrgContextDep,
                       resource_type: str | None = None, resource_id: str | None = None):
    org_id = _org(ctx)
    reaction = await CollaborationService(session).add_reaction(
        organization_id=org_id, user_id=ctx.user.id, emoji=body.emoji,
        comment_id=body.comment_id, resource_type=resource_type, resource_id=resource_id)
    await session.commit()
    return {"id": reaction.id, "emoji": reaction.emoji}


# --------------------------------------------------------------------------- #
# Personalization
# --------------------------------------------------------------------------- #
@router.get("/preferences")
async def get_preferences(session: DBSession, ctx: OrgContextDep):
    org_id = _org(ctx)
    return await PersonalizationService(session).get_prefs(
        user_id=ctx.user.id, organization_id=org_id)


@router.put("/preferences")
async def set_preference(body: PreferenceRequest, session: DBSession, ctx: OrgContextDep):
    try:
        await PersonalizationService(session).set_pref(
            user_id=ctx.user.id, key=body.key, value=body.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    await session.commit()
    return {"key": body.key, "value": body.value}


@router.post("/preferences/favorites")
async def toggle_favorite(item: dict, session: DBSession, ctx: OrgContextDep):
    favs = await PersonalizationService(session).toggle_favorite(
        user_id=ctx.user.id, item=item)
    await session.commit()
    return {"favorites": favs}


@router.post("/preferences/recent")
async def track_recent(item: dict, session: DBSession, ctx: OrgContextDep):
    recent = await PersonalizationService(session).track_recent(
        user_id=ctx.user.id, item=item)
    await session.commit()
    return {"recently_viewed": recent}


# --------------------------------------------------------------------------- #
# Product analytics
# --------------------------------------------------------------------------- #
@router.post("/analytics/track", status_code=status.HTTP_201_CREATED)
async def track_analytics(body: AnalyticsTrackRequest, session: DBSession,
                          ctx: OrgContextDep):
    org_id = _org(ctx)
    event = await ProductAnalyticsService(session).track(
        organization_id=org_id, user_id=ctx.user.id,
        event_name=body.event_name, properties=body.properties,
        session_id=body.session_id)
    await session.commit()
    return {"tracked": event is not None, "event_id": getattr(event, "id", None)}


@router.get("/analytics/summary")
async def analytics_summary(session: DBSession, ctx: OrgContextDep,
                            days: int = Query(30, ge=1, le=365)):
    org_id = _org(ctx)
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(status_code=403, detail="Admin required")
    return await ProductAnalyticsService(session).summary(organization_id=org_id, days=days)


# --------------------------------------------------------------------------- #
# Command palette
# --------------------------------------------------------------------------- #
@router.get("/commands", response_model=CommandPaletteResponse)
async def command_palette(session: DBSession, ctx: OrgContextDep,
                          q: str = Query(""), limit: int = Query(20, le=50)):
    org_id = _org(ctx)
    return await CommandPaletteService(session).query(
        organization_id=org_id, user_id=ctx.user.id, q=q, limit=limit)


# --------------------------------------------------------------------------- #
# Auto-generated documentation diagrams
# --------------------------------------------------------------------------- #
@router.get("/docs/diagrams")
async def documentation_diagrams(ctx: OrgContextDep):
    from app.services.documentation_generator import DocumentationGeneratorService

    return DocumentationGeneratorService.diagram_bundle()
