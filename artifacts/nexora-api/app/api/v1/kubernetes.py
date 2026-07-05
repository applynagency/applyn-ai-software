from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.kubernetes_agent import (
    KubernetesArtifactResponse,
    KubernetesRunListResponse,
    KubernetesRunRequest,
    KubernetesRunResponse,
)
from app.services.kubernetes import KubernetesService

router = APIRouter(prefix="/agents/kubernetes", tags=["Kubernetes"])


@router.post("/run", response_model=KubernetesRunResponse, status_code=201)
async def run_kubernetes_agent(
    data: KubernetesRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Kubernetes Agent against a requirement and its DevOps foundation output.

    Requires a completed CI/CD Agent run for the same requirement unless a run ID is specified.
    """
    service = KubernetesService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=KubernetesRunResponse)
async def get_kubernetes_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = KubernetesService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=KubernetesArtifactResponse)
async def get_kubernetes_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = KubernetesService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=KubernetesRunListResponse)
async def list_kubernetes_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List Kubernetes run history for a requirement."""
    service = KubernetesService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
