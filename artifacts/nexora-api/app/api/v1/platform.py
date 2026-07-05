"""Platform convergence API (Sprint 62A).

One surface for the converged cross-cutting capabilities:

* ``/v1/platform/events``        — domain event bus (publish/list/replay/DLQ)
* ``/v1/platform/notifications`` — unified notification platform
* ``/v1/platform/search``        — global search + autocomplete
* ``/v1/platform/activity``      — global activity feed
* ``/v1/platform/config``        — configuration platform (global/org/user)
* ``/v1/platform/plugins``       — plugin framework
* ``/v1/platform/executions``    — unified execution engine
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.auth.dependencies import DBSession
from app.auth.org_context import OrgContext, OrgContextDep
from app.models.organization import OrganizationRole
from app.platform.activity import ActivityService
from app.platform.config import ConfigService
from app.platform.events import EventBus
from app.platform.execution import ExecutionEngine, ExecutionError
from app.platform.notifications import NotificationService
from app.platform.plugins import PluginError, PluginService
from app.platform.search import SearchService
from app.schemas.platform import (
    ActivityResponse,
    ApprovalRequest,
    CheckpointRequest,
    ConfigMapResponse,
    ConfigSetRequest,
    ConfigValueResponse,
    EventPublishRequest,
    EventResponse,
    ExecutionSubmitRequest,
    NotificationResponse,
    NotificationSendRequest,
    NotificationTemplateRequest,
    OrganizationPluginResponse,
    PluginCatalogItem,
    PluginInstallRequest,
    SearchResponse,
)

router = APIRouter(prefix="/platform", tags=["Platform"])

_ADMIN_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN}


def _require_org_admin(ctx: OrgContext) -> str:
    org_id = ctx.requires_organization
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Organization admin role required")
    return org_id


# --------------------------------------------------------------------------- #
# Events
# --------------------------------------------------------------------------- #
@router.post("/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def publish_event(body: EventPublishRequest, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    event = await EventBus(session).publish(
        body.event_type, organization_id=org_id, payload=body.payload,
        aggregate_type=body.aggregate_type, aggregate_id=body.aggregate_id,
        actor_id=ctx.user.id, source=body.source)
    await session.commit()
    return event


@router.get("/events", response_model=list[EventResponse])
async def list_events(
    session: DBSession, ctx: OrgContextDep,
    event_type: str | None = None, status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, le=200), offset: int = 0,
):
    org_id = ctx.requires_organization
    return await EventBus(session).list_events(
        organization_id=org_id, event_type=event_type, status=status_filter,
        limit=limit, offset=offset)


@router.post("/events/{event_id}/replay", response_model=EventResponse)
async def replay_event(event_id: str, session: DBSession, ctx: OrgContextDep):
    _require_org_admin(ctx)
    event = await EventBus(session).replay(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    await session.commit()
    return event


@router.post("/events/{event_id}/requeue", response_model=EventResponse)
async def requeue_event(event_id: str, session: DBSession, ctx: OrgContextDep):
    _require_org_admin(ctx)
    event = await EventBus(session).requeue_dead_letter(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    await session.commit()
    return event


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #
@router.post("/notifications", response_model=NotificationResponse,
             status_code=status.HTTP_201_CREATED)
async def send_notification(body: NotificationSendRequest, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    try:
        message = await NotificationService(session).send(
            channel=body.channel, recipient=body.recipient, organization_id=org_id,
            template_key=body.template_key, locale=body.locale, context=body.context,
            subject=body.subject, body=body.body)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    await session.commit()
    return message


@router.get("/notifications", response_model=list[NotificationResponse])
async def list_notifications(
    session: DBSession, ctx: OrgContextDep,
    status_filter: str | None = Query(None, alias="status"),
    channel: str | None = None, limit: int = Query(50, le=200), offset: int = 0,
):
    org_id = ctx.requires_organization
    return await NotificationService(session).list_messages(
        organization_id=org_id, status=status_filter, channel=channel,
        limit=limit, offset=offset)


@router.post("/notifications/{message_id}/retry", response_model=NotificationResponse)
async def retry_notification(message_id: str, session: DBSession, ctx: OrgContextDep):
    _ = ctx.requires_organization
    message = await NotificationService(session).retry(message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="message not found")
    await session.commit()
    return message


@router.post("/notifications/templates", status_code=status.HTTP_201_CREATED)
async def upsert_notification_template(
    body: NotificationTemplateRequest, session: DBSession, ctx: OrgContextDep,
):
    org_id = _require_org_admin(ctx)
    template = await NotificationService(session).upsert_template(
        key=body.key, channel=body.channel, body_template=body.body_template,
        subject_template=body.subject_template, locale=body.locale,
        organization_id=None if body.scope_global else org_id, created_by=ctx.user.id)
    await session.commit()
    return {"id": template.id, "key": template.key, "channel": template.channel,
            "locale": template.locale}


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
@router.get("/search", response_model=SearchResponse)
async def global_search(
    session: DBSession, ctx: OrgContextDep,
    q: str = Query(..., min_length=1),
    types: str | None = Query(None, description="comma-separated entity types"),
    semantic: bool = False, limit: int = Query(20, le=100), offset: int = 0,
):
    org_id = ctx.requires_organization
    type_list = [t.strip() for t in types.split(",")] if types else None
    return await SearchService(session).search(
        q, organization_id=org_id, types=type_list, limit=limit, offset=offset,
        semantic=semantic)


@router.get("/search/autocomplete")
async def search_autocomplete(
    session: DBSession, ctx: OrgContextDep,
    q: str = Query(..., min_length=1), limit: int = Query(10, le=25),
):
    org_id = ctx.requires_organization
    return {"suggestions": await SearchService(session).autocomplete(
        q, organization_id=org_id, limit=limit)}


# --------------------------------------------------------------------------- #
# Activity feed
# --------------------------------------------------------------------------- #
@router.get("/activity", response_model=list[ActivityResponse])
async def list_activity(
    session: DBSession, ctx: OrgContextDep,
    actor_id: str | None = None, object_type: str | None = None,
    object_id: str | None = None, limit: int = Query(50, le=200), offset: int = 0,
):
    org_id = ctx.requires_organization
    return await ActivityService(session).list(
        organization_id=org_id, actor_id=actor_id, object_type=object_type,
        object_id=object_id, limit=limit, offset=offset)


@router.get("/activity/me", response_model=list[ActivityResponse])
async def my_activity(
    session: DBSession, ctx: OrgContextDep, limit: int = Query(50, le=200), offset: int = 0,
):
    org_id = ctx.requires_organization
    return await ActivityService(session).list(
        organization_id=org_id, actor_id=ctx.user.id, limit=limit, offset=offset)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
@router.put("/config", response_model=ConfigValueResponse)
async def set_config(body: ConfigSetRequest, session: DBSession, ctx: OrgContextDep):
    scope = body.scope
    if scope == "global":
        if not ctx.user.is_superuser:
            raise HTTPException(status_code=403, detail="superuser required for global config")
        scope_id = None
    elif scope == "user":
        scope_id = ctx.user.id
    else:
        scope = "organization"
        scope_id = _require_org_admin(ctx)
    await ConfigService(session).set(
        key=body.key, value=body.value, scope=scope, scope_id=scope_id,
        is_feature_flag=body.is_feature_flag, is_secret_ref=body.is_secret_ref,
        updated_by=ctx.user.id)
    await session.commit()
    return ConfigValueResponse(key=body.key, value=body.value)


@router.get("/config/{key}", response_model=ConfigValueResponse)
async def get_config(key: str, session: DBSession, ctx: OrgContextDep):
    value = await ConfigService(session).get(
        key, organization_id=ctx.organization_id, user_id=ctx.user.id)
    return ConfigValueResponse(key=key, value=value)


@router.get("/config", response_model=ConfigMapResponse)
async def resolve_config(session: DBSession, ctx: OrgContextDep):
    values = await ConfigService(session).resolve_all(
        organization_id=ctx.organization_id, user_id=ctx.user.id)
    return ConfigMapResponse(values=values)


# --------------------------------------------------------------------------- #
# Plugins
# --------------------------------------------------------------------------- #
@router.get("/plugins/catalog", response_model=list[PluginCatalogItem])
async def plugin_catalog(session: DBSession, ctx: OrgContextDep):
    _ = ctx.requires_organization
    return await PluginService(session).list_catalog()


@router.get("/plugins", response_model=list[OrganizationPluginResponse])
async def list_installed_plugins(session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    return await PluginService(session).list_installed(org_id)


@router.get("/plugins/capabilities")
async def plugin_capabilities(session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    return await PluginService(session).capabilities(org_id)


@router.post("/plugins/install", response_model=OrganizationPluginResponse,
             status_code=status.HTTP_201_CREATED)
async def install_plugin(body: PluginInstallRequest, session: DBSession, ctx: OrgContextDep):
    org_id = _require_org_admin(ctx)
    try:
        inst = await PluginService(session).install(
            organization_id=org_id, slug=body.slug, installed_by=ctx.user.id,
            config=body.config)
    except PluginError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    await session.commit()
    return inst


@router.post("/plugins/{slug}/{action}", response_model=OrganizationPluginResponse)
async def plugin_lifecycle(slug: str, action: str, session: DBSession, ctx: OrgContextDep):
    org_id = _require_org_admin(ctx)
    svc = PluginService(session)
    try:
        if action == "enable":
            inst = await svc.enable(organization_id=org_id, slug=slug)
        elif action == "disable":
            inst = await svc.disable(organization_id=org_id, slug=slug)
        elif action == "upgrade":
            inst = await svc.upgrade(organization_id=org_id, slug=slug)
        else:
            raise HTTPException(status_code=400, detail=f"unknown action '{action}'")
    except PluginError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    await session.commit()
    return inst


@router.delete("/plugins/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def uninstall_plugin(slug: str, session: DBSession, ctx: OrgContextDep):
    org_id = _require_org_admin(ctx)
    await PluginService(session).uninstall(organization_id=org_id, slug=slug)
    await session.commit()


# --------------------------------------------------------------------------- #
# Execution engine
# --------------------------------------------------------------------------- #
@router.post("/executions", status_code=status.HTTP_202_ACCEPTED)
async def submit_execution(body: ExecutionSubmitRequest, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    try:
        return await ExecutionEngine(session).submit(
            task_name=body.task_name, job_type=body.job_type, organization_id=org_id,
            user_id=ctx.user.id, params=body.params, priority=body.priority,
            delay_seconds=body.delay_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.get("/executions/{run_id}")
async def get_execution(run_id: str, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    data = await ExecutionEngine(session).get(run_id, organization_id=org_id)
    if data is None:
        raise HTTPException(status_code=404, detail="run not found")
    return data


@router.post("/executions/{run_id}/cancel")
async def cancel_execution(run_id: str, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    try:
        ok = await ExecutionEngine(session).cancel(run_id, organization_id=org_id)
    except ExecutionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    await session.commit()
    return {"cancelled": ok}


@router.post("/executions/{run_id}/retry")
async def retry_execution(run_id: str, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    try:
        return await ExecutionEngine(session).retry(run_id, organization_id=org_id)
    except ExecutionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.post("/executions/{run_id}/checkpoint")
async def checkpoint_execution(
    run_id: str, body: CheckpointRequest, session: DBSession, ctx: OrgContextDep,
):
    org_id = ctx.requires_organization
    cp = await ExecutionEngine(session).checkpoint(
        run_id, label=body.label, state=body.state, organization_id=org_id)
    await session.commit()
    return {"id": cp.id, "sequence": cp.sequence, "label": cp.label}


@router.post("/executions/{run_id}/resume")
async def resume_execution(run_id: str, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    try:
        return await ExecutionEngine(session).resume(run_id, organization_id=org_id)
    except ExecutionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.post("/executions/{run_id}/approve")
async def approve_execution(
    run_id: str, body: ApprovalRequest, session: DBSession, ctx: OrgContextDep,
):
    org_id = _require_org_admin(ctx)
    try:
        return await ExecutionEngine(session).approve(
            run_id, approver_id=ctx.user.id, organization_id=org_id)
    except ExecutionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
