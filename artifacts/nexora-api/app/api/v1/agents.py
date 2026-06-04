from fastapi import APIRouter, Query
from typing import Optional
from app.auth.dependencies import CurrentUser, DBSession
from app.schemas.agent import AgentRunRequest, AgentRunResponse
from app.workflows.engine import AgentWorkflowEngine
from app.repositories.agent import AgentRunRepository

router = APIRouter(prefix="/agents", tags=["AI Agents"])


@router.post("/product-owner/run", response_model=AgentRunResponse, status_code=202)
async def run_product_owner_agent(
    data: AgentRunRequest, current_user: CurrentUser, session: DBSession
):
    """
    Trigger the Product Owner Agent to analyze a business requirement.

    The agent will:
    1. Analyze the requirement
    2. Generate Epics, Features, and User Stories
    3. Create Acceptance Criteria and Story Points
    4. Produce a Sprint Plan and Risk Analysis
    """
    from app.models.agent import AgentType
    data.agent_type = AgentType.PRODUCT_OWNER
    engine = AgentWorkflowEngine(session)
    return await engine.execute(data, current_user)


@router.get("/runs", response_model=dict)
async def list_agent_runs(
    current_user: CurrentUser,
    session: DBSession,
    requirement_id: Optional[str] = Query(default=None, description="Filter by requirement ID"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """List agent runs, optionally filtered by requirement."""
    run_repo = AgentRunRepository(session)
    if requirement_id:
        items, total = await run_repo.list_by_requirement(requirement_id, offset=offset, limit=limit)
    else:
        items, total = await run_repo.list_all(offset=offset, limit=limit)
    return {"items": [AgentRunResponse.model_validate(r) for r in items], "total": total}


@router.get("/runs/{run_id}", response_model=AgentRunResponse)
async def get_agent_run(run_id: str, current_user: CurrentUser, session: DBSession):
    """Get details and output of a specific agent run."""
    run_repo = AgentRunRepository(session)
    run = await run_repo.get_with_outputs(run_id)
    if not run:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("AgentRun", run_id)

    response = AgentRunResponse.model_validate(run)
    if run.outputs:
        from app.schemas.agent import ProductOwnerOutput
        latest = sorted(run.outputs, key=lambda o: o.version, reverse=True)[0]
        try:
            response.output = ProductOwnerOutput(**latest.content)
        except Exception:
            pass

    return response
