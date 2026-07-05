from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.docker_agent import (
    DockerAgentArtifactResponse,
    DockerAgentRunListResponse,
    DockerAgentRunRequest,
    DockerAgentRunResponse,
)
from app.services.docker_agent import DockerAgentService

router = APIRouter(prefix="/agents/docker-agent", tags=["Docker Agent"])


@router.post("/run", response_model=DockerAgentRunResponse, status_code=201)
async def run_docker_agent(
    data: DockerAgentRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the Docker Agent against a requirement and infrastructure architecture output.

    Requires a completed Infrastructure Architect run for the same requirement
    unless a run ID is specified.
    """
    service = DockerAgentService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=DockerAgentRunResponse)
async def get_docker_agent_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = DockerAgentService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=DockerAgentArtifactResponse)
async def get_docker_agent_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = DockerAgentService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=DockerAgentRunListResponse)
async def list_docker_agent_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List Docker Agent run history for a requirement."""
    service = DockerAgentService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
