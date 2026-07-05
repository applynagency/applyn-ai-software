from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.lifecycle.orchestrator import LifecycleOrchestratorService
from app.schemas.deployment import (
    DeploymentArtifactResponse,
    DeploymentRunListResponse,
    DeploymentRunRequest,
    DeploymentRunResponse,
)
from app.services.deployment import DeploymentService

router = APIRouter(prefix="/agents/deployment", tags=["Deployment"])


@router.post("/run", response_model=DeploymentRunResponse, status_code=201)
async def run_deployment_agent(
    data: DeploymentRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Deploy an application package to a cloud provider.

    Automatically resolves build, assembly, and approval prerequisites.
    """
    orchestrator = LifecycleOrchestratorService(session)
    return await orchestrator.deploy_application(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=DeploymentRunResponse)
async def get_deployment_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """Alias for ``GET /v1/deployments/{deployment_id}`` (SDK compatibility)."""
    return await DeploymentService(session).get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=DeploymentArtifactResponse)
async def get_deployment_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = DeploymentService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=DeploymentRunListResponse)
async def list_deployment_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    service = DeploymentService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
