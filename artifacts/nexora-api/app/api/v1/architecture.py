"""Sprint 46B - Architecture Discovery & Service Map API.

* POST /v1/architecture/discover    - run topology discovery (persist a snapshot)
* GET  /v1/architecture             - list discovery snapshots
* GET  /v1/architecture/dashboard   - latest map + risk areas + trend
* GET  /v1/architecture/{id}        - full snapshot (service map + edges + risks)

Read-only over connected platform signals; never modifies infrastructure.
Org-scoped and audited.
"""

from fastapi import APIRouter, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.architecture import (
    ArchitectureDashboard,
    SnapshotResponse,
    SnapshotSummary,
)
from app.services.architecture import ArchitectureDiscoveryService

router = APIRouter(prefix="/architecture", tags=["Architecture Discovery"])


@router.post("/discover", response_model=SnapshotResponse, status_code=status.HTTP_201_CREATED)
async def discover(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await ArchitectureDiscoveryService(session).discover(current_user, org_context)


@router.get("", response_model=list[SnapshotSummary])
async def list_snapshots(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    rows = await ArchitectureDiscoveryService(session).list(current_user, org_context)
    return [SnapshotSummary.model_validate(r) for r in rows]


@router.get("/dashboard", response_model=ArchitectureDashboard)
async def dashboard(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await ArchitectureDiscoveryService(session).dashboard(current_user, org_context)


@router.get("/{snapshot_id}", response_model=SnapshotResponse)
async def get_snapshot(
    snapshot_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    return await ArchitectureDiscoveryService(session).get(current_user, org_context, snapshot_id)
