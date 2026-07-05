"""Sprint 52C.1 — Demo Scenario Engine API.

POST   /v1/demo-scenarios/seed          - seed all 5 built-in scenarios for an org
GET    /v1/demo-scenarios               - list scenarios for the current org
GET    /v1/demo-scenarios/{id}          - get a single scenario
POST   /v1/demo-scenarios/{id}/run      - execute a scenario
POST   /v1/demo-scenarios/{id}/replay   - replay a scenario (optionally from a specific run)
POST   /v1/demo-scenarios/{id}/reset    - delete all runs, reset run count
GET    /v1/demo-scenarios/runs          - list all runs for the current org
GET    /v1/demo-scenarios/{id}/runs     - list runs for a specific scenario

All routes require authentication and an organisation context
(X-Organization-Id header via OrgContextDep).
"""

from fastapi import APIRouter

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.demo_scenario import (
    ScenarioListResponse,
    ScenarioRunListResponse,
    ScenarioRunRequest,
    ScenarioRunView,
    ScenarioView,
)
from app.services.demo_scenario import DemoScenarioService

router = APIRouter(prefix="/demo-scenarios", tags=["Demo Scenarios"])


@router.post("/seed", response_model=list[ScenarioView], status_code=201)
async def seed_scenarios(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    """Idempotently seed all 5 built-in scenarios for the current organisation."""
    org_id = org_context.requires_organization
    svc = DemoScenarioService(session)
    created = await svc.seed_for_org(org_id, current_user)
    return created


@router.get("/runs", response_model=ScenarioRunListResponse)
async def list_all_runs(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    org_id = org_context.requires_organization
    svc = DemoScenarioService(session)
    items = await svc.list_runs(org_id, current_user)
    return ScenarioRunListResponse(items=items, total=len(items))


@router.get("", response_model=ScenarioListResponse)
async def list_scenarios(
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    org_id = org_context.requires_organization
    svc = DemoScenarioService(session)
    items = await svc.list_scenarios(org_id, current_user)
    return ScenarioListResponse(items=items, total=len(items))


@router.get("/{scenario_id}", response_model=ScenarioView)
async def get_scenario(
    scenario_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    org_id = org_context.requires_organization
    svc = DemoScenarioService(session)
    return await svc.get_scenario(org_id, scenario_id, current_user)


@router.post("/{scenario_id}/run", response_model=ScenarioRunView, status_code=201)
async def run_scenario(
    scenario_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    org_id = org_context.requires_organization
    svc = DemoScenarioService(session)
    return await svc.run_scenario(org_id, scenario_id, current_user)


@router.post("/{scenario_id}/replay", response_model=ScenarioRunView, status_code=201)
async def replay_scenario(
    scenario_id: str,
    payload: ScenarioRunRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    org_id = org_context.requires_organization
    svc = DemoScenarioService(session)
    return await svc.replay_scenario(
        org_id, scenario_id, payload.run_id, current_user
    )


@router.post("/{scenario_id}/reset", response_model=ScenarioView)
async def reset_scenario(
    scenario_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    org_id = org_context.requires_organization
    svc = DemoScenarioService(session)
    return await svc.reset_scenario(org_id, scenario_id, current_user)


@router.get("/{scenario_id}/runs", response_model=ScenarioRunListResponse)
async def list_scenario_runs(
    scenario_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    org_id = org_context.requires_organization
    svc = DemoScenarioService(session)
    items = await svc.list_runs(org_id, current_user, scenario_id=scenario_id)
    return ScenarioRunListResponse(items=items, total=len(items))
