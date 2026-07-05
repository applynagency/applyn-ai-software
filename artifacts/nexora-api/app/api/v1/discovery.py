"""Discovery API — the single, unified discovery surface (``/v1/discovery``).

One discovery system across every connected integration (read-only): assets are
the Universal Resource Model (``DiscoveredAsset``) and the graph is the Platform
Knowledge Graph (``KnowledgeGraphNode`` / ``KnowledgeGraphEdge``).

* POST /v1/discovery/sync     - run discovery across all connected integrations
* GET  /v1/discovery/summary  - inventory summary (domains, providers, counts)
* GET  /v1/discovery/progress - latest scan-run progress
* GET  /v1/discovery/assets   - the discovered inventory (filterable)
* GET  /v1/discovery/graph    - the knowledge graph (nodes + edges)
* GET  /v1/discovery/events   - discovery change timeline
* GET  /v1/discovery/context  - the discovered context the AI consumes

Read-only w.r.t. customer infrastructure (no mutations). Org-scoped & audited.
"""

from fastapi import APIRouter, Query, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.core.config import settings
from app.schemas.discovery_pipeline import ScanProgressView
from app.schemas.universal_discovery import (
    AIContextResponse,
    DiscoveryEventView,
    KnowledgeGraphView,
    UniversalAssetView,
    UniversalDiscoverySummary,
    UniversalSyncRequest,
    UniversalSyncResponse,
)
from app.services.universal_discovery import UniversalDiscoveryService

router = APIRouter(prefix="/discovery", tags=["Discovery"])


@router.post("/sync", response_model=UniversalSyncResponse, status_code=status.HTTP_201_CREATED)
async def sync_discovery(
    payload: UniversalSyncRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """Run discovery across ALL connected integrations now (read-only)."""
    if settings.JOB_QUEUE_ENABLED:
        from app.jobs.submit import accepted_response, submit_job
        from app.models.job import JobType

        org_id = org_context.requires_organization
        kwargs = {
            "organization_id": org_id, "user_id": current_user.id,
            "providers": payload.providers,
        }
        job = await submit_job(
            session, task_name="run_universal_discovery",
            job_type=JobType.UNIVERSAL_DISCOVERY,
            organization_id=org_id, user_id=current_user.id, params=kwargs, task_kwargs=kwargs,
        )
        return accepted_response(job)
    return await UniversalDiscoveryService(session).run_for_org(
        current_user, org_context, providers_filter=payload.providers,
    )


@router.get("/summary", response_model=UniversalDiscoverySummary)
async def discovery_summary(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await UniversalDiscoveryService(session).summary(current_user, org_context)


@router.get("/progress", response_model=ScanProgressView | None)
async def discovery_progress(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await UniversalDiscoveryService(session).progress(current_user, org_context)


@router.get("/assets", response_model=list[UniversalAssetView])
async def discovery_assets(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    domain: str | None = Query(None),
    provider: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
):
    return await UniversalDiscoveryService(session).list_assets(
        current_user, org_context, domain=domain, provider=provider, limit=limit)


@router.get("/graph", response_model=KnowledgeGraphView)
async def discovery_graph(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await UniversalDiscoveryService(session).graph(current_user, org_context)


@router.get("/events", response_model=list[DiscoveryEventView])
async def discovery_events(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    limit: int = Query(100, ge=1, le=500),
):
    return await UniversalDiscoveryService(session).timeline(
        current_user, org_context, limit=limit)


@router.get("/context", response_model=AIContextResponse)
async def discovery_context(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    subject: str = Query(..., min_length=1),
):
    """The discovered context (repos/deployments/owners/channels/services) the
    AI consumes for a given service or incident subject."""
    return await UniversalDiscoveryService(session).ai_context(
        current_user, org_context, subject)
