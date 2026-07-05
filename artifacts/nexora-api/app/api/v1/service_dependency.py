"""Sprint 44B — Service Dependency Graph & Blast Radius API (read-only).

* POST   /v1/service-dependencies            — create a dependency edge
* GET    /v1/service-dependencies            — list dependency edges
* GET    /v1/service-dependencies/graph      — full graph (nodes + edges) for viz
* DELETE /v1/service-dependencies/{id}       — delete a dependency edge
* GET    /v1/services/{id}/dependencies      — per-service upstream/downstream
* GET    /v1/incidents/{id}/blast-radius     — incident blast radius
* GET    /v1/blast-radius/dashboard          — org-wide blast-radius dashboard

Read-only intelligence: never deploys, remediates, or mutates infrastructure.
Org-scoped and audited.
"""

from fastapi import APIRouter, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.service_dependency import (
    BlastRadius,
    BlastRadiusDashboard,
    DependencyCreate,
    DependencyEdge,
    DependencyGraph,
    ServiceDependencyView,
)
from app.services.dependency_graph import DependencyGraphService

router = APIRouter(tags=["Service Dependencies"])


@router.post("/service-dependencies", response_model=DependencyEdge, status_code=status.HTTP_201_CREATED)
async def create_dependency(
    data: DependencyCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await DependencyGraphService(session).add_dependency(current_user, org_context, data)


@router.get("/service-dependencies", response_model=list[DependencyEdge])
async def list_dependencies(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await DependencyGraphService(session).list_dependencies(current_user, org_context)


@router.get("/service-dependencies/graph", response_model=DependencyGraph)
async def dependency_graph(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await DependencyGraphService(session).graph(current_user, org_context)


@router.delete("/service-dependencies/{dependency_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dependency(
    dependency_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    await DependencyGraphService(session).delete_dependency(current_user, org_context, dependency_id)


@router.get("/services/{service_id}/dependencies", response_model=ServiceDependencyView)
async def service_dependencies(
    service_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await DependencyGraphService(session).service_dependencies(current_user, org_context, service_id)


@router.get("/incidents/{incident_id}/blast-radius", response_model=BlastRadius)
async def incident_blast_radius(
    incident_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await DependencyGraphService(session).blast_radius(current_user, org_context, incident_id)


@router.get("/blast-radius/dashboard", response_model=BlastRadiusDashboard)
async def blast_radius_dashboard(
    current_user: CurrentUser, session: DBSession, org_context: OrgContextDep
):
    return await DependencyGraphService(session).dashboard(current_user, org_context)
