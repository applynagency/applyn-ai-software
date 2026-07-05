from fastapi import APIRouter, Query

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.qa_architect import (
    QAArchitectArtifactResponse,
    QAArchitectRunListResponse,
    QAArchitectRunRequest,
    QAArchitectRunResponse,
)
from app.services.qa_architect import QAArchitectService

router = APIRouter(prefix="/agents/qa-architect", tags=["QA Architect"])


@router.post("/run", response_model=QAArchitectRunResponse, status_code=201)
async def run_qa_architect_agent(
    data: QAArchitectRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """
    Run the QA Architect agent against a requirement and execution outputs.

    Requires completed Frontend Execution and Backend Execution runs for the
    same requirement unless run IDs are specified.
    """
    service = QAArchitectService(session)
    return await service.run(data, current_user, org_context)


@router.get("/runs/{run_id}", response_model=QAArchitectRunResponse)
async def get_qa_architect_run(
    run_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = QAArchitectService(session)
    return await service.get_run(run_id, current_user, org_context)


@router.get("/artifacts/{artifact_id}", response_model=QAArchitectArtifactResponse)
async def get_qa_architect_artifact(
    artifact_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    service = QAArchitectService(session)
    return await service.get_artifact(artifact_id, current_user, org_context)


@router.get("/{requirement_id}", response_model=QAArchitectRunListResponse)
async def list_qa_architect_runs_for_requirement(
    requirement_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List QA Architect run history for a requirement."""
    service = QAArchitectService(session)
    return await service.list_by_requirement(
        requirement_id, current_user, org_context, offset=offset, limit=limit
    )
