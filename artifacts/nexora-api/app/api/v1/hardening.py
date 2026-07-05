"""Production-hardening admin API (Sprint 62B).

Operational + observability control plane that complements the platform router:

* ``/v1/ops/*``                 — maintenance mode, kill switches, feature rollout,
                                  diagnostics, support bundle, config export/import
* ``/v1/platform/events/replay`` — replay by time range / org / type + drain
* ``/v1/ai/health``             — AI provider circuit-breaker health + token budget
* ``/v1/platform/executions/recover`` + ``/analytics``
* ``/v1/platform/search/analytics``
* ``/v1/platform/graph/analytics``

Admin-gated (org owner/admin or superuser). Read endpoints that expose only the
caller's org data are available to any org member.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from app.auth.dependencies import DBSession
from app.auth.org_context import OrgContext, OrgContextDep
from app.models.organization import OrganizationRole

router = APIRouter(tags=["Operations"])

_ADMIN_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN}


def _require_org_admin(ctx: OrgContext) -> str:
    org_id = ctx.requires_organization
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Organization admin role required")
    return org_id


def _require_superuser(ctx: OrgContext) -> None:
    if not ctx.user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Superuser role required")


# --------------------------------------------------------------------------- #
# Operations control plane
# --------------------------------------------------------------------------- #
@router.get("/ops/diagnostics")
async def ops_diagnostics(session: DBSession, ctx: OrgContextDep):
    _ = _require_org_admin(ctx)
    from app.platform.operations import OperationsService

    return await OperationsService(session).diagnostics()


@router.get("/ops/maintenance")
async def get_maintenance(session: DBSession, ctx: OrgContextDep):
    _ = ctx.requires_organization
    from app.platform.operations import OperationsService

    return await OperationsService(session).maintenance_status()


@router.post("/ops/maintenance")
async def set_maintenance(
    session: DBSession, ctx: OrgContextDep,
    enabled: bool = Query(...), message: str | None = None,
):
    _require_superuser(ctx)
    from app.platform.operations import OperationsService

    result = await OperationsService(session).set_maintenance(
        enabled, message=message, updated_by=ctx.user.id)
    await session.commit()
    return result


@router.post("/ops/kill-switch/{name}")
async def set_kill_switch(name: str, session: DBSession, ctx: OrgContextDep,
                          enabled: bool = Query(...)):
    _require_superuser(ctx)
    from app.platform.operations import OperationsService

    result = await OperationsService(session).set_kill_switch(
        name, enabled, updated_by=ctx.user.id)
    await session.commit()
    return result


@router.post("/ops/rollout/{feature}")
async def set_rollout(feature: str, session: DBSession, ctx: OrgContextDep,
                      percent: int = Query(..., ge=0, le=100)):
    _require_superuser(ctx)
    from app.platform.operations import OperationsService

    result = await OperationsService(session).set_rollout(
        feature, percent, updated_by=ctx.user.id)
    await session.commit()
    return result


@router.get("/ops/support-bundle")
async def support_bundle(session: DBSession, ctx: OrgContextDep):
    org_id = _require_org_admin(ctx)
    from app.platform.operations import OperationsService

    return await OperationsService(session).support_bundle(organization_id=org_id)


@router.get("/ops/config/export")
async def export_config(session: DBSession, ctx: OrgContextDep):
    org_id = _require_org_admin(ctx)
    from app.platform.operations import OperationsService

    return await OperationsService(session).export_config(organization_id=org_id)


@router.post("/ops/config/import")
async def import_config(bundle: dict, session: DBSession, ctx: OrgContextDep):
    _require_superuser(ctx)
    from app.platform.operations import OperationsService

    count = await OperationsService(session).import_config(bundle, updated_by=ctx.user.id)
    await session.commit()
    return {"imported": count}


# --------------------------------------------------------------------------- #
# Event replay (by time range / org / type) + drain
# --------------------------------------------------------------------------- #
@router.post("/platform/events/replay")
async def replay_events(
    session: DBSession, ctx: OrgContextDep,
    since: datetime | None = None, until: datetime | None = None,
    event_type: str | None = None,
):
    org_id = _require_org_admin(ctx)
    from app.platform.events import EventBus

    count = await EventBus(session).replay_range(
        since=since, until=until, organization_id=org_id, event_type=event_type)
    await session.commit()
    return {"replayed": count}


@router.post("/platform/events/drain")
async def drain_events(session: DBSession, ctx: OrgContextDep,
                       limit: int = Query(100, le=1000)):
    _require_superuser(ctx)
    from app.platform.events import EventBus

    bus = EventBus(session)
    result = await bus.drain_pending(limit=limit)
    await session.commit()
    return result


@router.get("/platform/events/pending")
async def events_pending(session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    from app.platform.events import EventBus

    return {"pending": await EventBus(session).pending_count(organization_id=org_id)}


# --------------------------------------------------------------------------- #
# AI platform health + budget
# --------------------------------------------------------------------------- #
@router.get("/ai/health")
async def ai_health(ctx: OrgContextDep):
    _ = ctx.requires_organization
    from app.ai.health import get_provider_health

    return {"providers": get_provider_health().snapshot()}


@router.get("/ai/budget")
async def ai_budget(session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    from app.ai.budget import TokenBudget

    return await TokenBudget(session).status(org_id)


# --------------------------------------------------------------------------- #
# Execution recovery + analytics
# --------------------------------------------------------------------------- #
@router.post("/platform/executions/recover")
async def recover_executions(session: DBSession, ctx: OrgContextDep):
    _require_superuser(ctx)
    from app.platform.execution import ExecutionEngine

    result = await ExecutionEngine(session).recover_stalled()
    return result


@router.get("/platform/executions/analytics")
async def execution_analytics(session: DBSession, ctx: OrgContextDep):
    org_id = _require_org_admin(ctx)
    from app.platform.execution import ExecutionEngine

    return await ExecutionEngine(session).analytics(organization_id=org_id)


# --------------------------------------------------------------------------- #
# Search + graph analytics
# --------------------------------------------------------------------------- #
@router.get("/platform/search/analytics")
async def search_analytics(session: DBSession, ctx: OrgContextDep,
                           days: int = Query(7, ge=1, le=90)):
    org_id = _require_org_admin(ctx)
    from app.platform.search import SearchService

    return await SearchService(session).analytics(organization_id=org_id, days=days)


@router.post("/platform/search/reindex")
async def reindex_search(session: DBSession, ctx: OrgContextDep):
    org_id = _require_org_admin(ctx)
    from app.platform.search import SearchIndexer

    count = await SearchIndexer(session).reindex_org(org_id)
    await session.commit()
    return {"indexed": count}


@router.get("/platform/graph/analytics")
async def graph_analytics(session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    from app.services.graph import GraphService

    return await GraphService(session).analytics(org_id)
