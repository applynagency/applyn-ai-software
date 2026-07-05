"""AI Platform Operator REST API (Sprint 64B)."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.auth.dependencies import CurrentUser, DBSession
from app.auth.org_context import OrgContextDep
from app.schemas.ai_operator import (
    AIContextView,
    AnalyzeRequest,
    DashboardView,
    ExecutiveBriefingView,
    GoalCreate,
    GoalView,
    LearningView,
    PolicyCreate,
    PolicyView,
    ProposalView,
    RecommendationView,
    SavingsView,
    SimulationView,
    TimelineView,
)
from app.services.ai_operator import AIOperatorService

router = APIRouter(prefix="/operator", tags=["AI Platform Operator"])


def _svc(session) -> AIOperatorService:
    return AIOperatorService(session)


@router.get("/dashboard", response_model=DashboardView)
async def dashboard(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).dashboard(current_user, org_context)
    await session.commit()
    return DashboardView(**data)


@router.post("/analyze", response_model=list[RecommendationView])
async def analyze(
    payload: AnalyzeRequest,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
):
    rows = await _svc(session).analyze(current_user, org_context, trigger=payload.trigger)
    await session.commit()
    return [RecommendationView.model_validate(r) for r in rows]


@router.get("/recommendations", response_model=list[RecommendationView])
async def list_recommendations(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_recommendations(current_user, org_context)
    await session.commit()
    return [RecommendationView.model_validate(r) for r in rows]


@router.get("/recommendations/{recommendation_id}", response_model=RecommendationView)
async def get_recommendation(
    recommendation_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).get_recommendation(current_user, org_context, recommendation_id)
    await session.commit()
    return RecommendationView.model_validate(row)


@router.post(
    "/recommendations/{recommendation_id}/simulate",
    response_model=SimulationView,
    status_code=status.HTTP_201_CREATED,
)
async def simulate_recommendation(
    recommendation_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).simulate(current_user, org_context, recommendation_id)
    await session.commit()
    return SimulationView.model_validate(row)


@router.post(
    "/recommendations/{recommendation_id}/propose",
    response_model=ProposalView,
    status_code=status.HTTP_201_CREATED,
)
async def propose_action(
    recommendation_id: str, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).propose_action(current_user, org_context, recommendation_id)
    await session.commit()
    return ProposalView.model_validate(row)


@router.get("/proposals", response_model=list[ProposalView])
async def list_proposals(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_proposals(current_user, org_context)
    await session.commit()
    return [ProposalView.model_validate(r) for r in rows]


@router.post("/proposals/{proposal_id}/decide", response_model=ProposalView)
async def decide_proposal(
    proposal_id: str,
    current_user: CurrentUser,
    session: DBSession,
    org_context: OrgContextDep,
    approved: bool = Query(...),
):
    row = await _svc(session).decide_proposal(current_user, org_context, proposal_id, approved=approved)
    await session.commit()
    return ProposalView.model_validate(row)


@router.get("/policies", response_model=list[PolicyView])
async def list_policies(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_policies(current_user, org_context)
    await session.commit()
    return [PolicyView.model_validate(r) for r in rows]


@router.post("/policies", response_model=PolicyView, status_code=status.HTTP_201_CREATED)
async def create_policy(
    payload: PolicyCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).create_policy(current_user, org_context, payload)
    await session.commit()
    return PolicyView.model_validate(row)


@router.get("/goals", response_model=list[GoalView])
async def list_goals(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_goals(current_user, org_context)
    await session.commit()
    return [GoalView.model_validate(r) for r in rows]


@router.post("/goals", response_model=GoalView, status_code=status.HTTP_201_CREATED)
async def create_goal(
    payload: GoalCreate, current_user: CurrentUser, session: DBSession, org_context: OrgContextDep,
):
    row = await _svc(session).create_goal(current_user, org_context, payload)
    await session.commit()
    return GoalView.model_validate(row)


@router.get("/history", response_model=list[TimelineView])
async def history(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_timeline(current_user, org_context)
    await session.commit()
    return [TimelineView.model_validate(r) for r in rows]


@router.get("/learning", response_model=list[LearningView])
async def learning(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_learning(current_user, org_context)
    await session.commit()
    return [LearningView.model_validate(r) for r in rows]


@router.get("/simulations", response_model=list[SimulationView])
async def list_simulations(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    rows = await _svc(session).list_simulations(current_user, org_context)
    await session.commit()
    return [SimulationView.model_validate(r) for r in rows]


@router.get("/savings", response_model=SavingsView)
async def savings(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).savings(current_user, org_context)
    await session.commit()
    return SavingsView(**data)


@router.post("/executive/briefing", response_model=ExecutiveBriefingView, status_code=status.HTTP_201_CREATED)
async def generate_executive_briefing(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    row = await _svc(session).generate_executive_briefing(current_user, org_context)
    await session.commit()
    return ExecutiveBriefingView.model_validate(row)


@router.get("/executive/latest", response_model=ExecutiveBriefingView | None)
async def latest_executive_briefing(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    row = await _svc(session).latest_executive_briefing(current_user, org_context)
    await session.commit()
    return ExecutiveBriefingView.model_validate(row) if row else None


@router.get("/ai-context", response_model=AIContextView)
async def ai_context(current_user: CurrentUser, session: DBSession, org_context: OrgContextDep):
    data = await _svc(session).ai_context(current_user, org_context)
    await session.commit()
    return AIContextView(**data)
