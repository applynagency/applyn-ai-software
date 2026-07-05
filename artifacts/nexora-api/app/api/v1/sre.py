"""Autonomous SRE API (Sprint 63B).

* ``/v1/sre/commander``        — AI incident commander (AgentRuntime)
* ``/v1/sre/rca``              — grounded root-cause analysis
* ``/v1/sre/runbooks``         — executable runbooks (ExecutionEngine)
* ``/v1/sre/remediation``      — approval-gated remediation workflows
* ``/v1/sre/change-risk``      — pre-deploy change risk assessment
* ``/v1/sre/predictions``      — predictive reliability
* ``/v1/sre/ops-center``       — unified AI operations dashboard
* ``/v1/sre/reports``          — executive AI reports
* ``/v1/sre/learning``         — post-incident knowledge capture
* ``/v1/sre/recommendations``  — explainable AI recommendations
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.auth.dependencies import DBSession
from app.auth.org_context import OrgContext, OrgContextDep
from app.models.organization import OrganizationRole
from app.models.sre import SREAIRecommendation
from app.platform.sre import (
    ChangeRiskEngineService,
    ExecutableRunbookService,
    ExecutiveAIReportService,
    ExplainabilityService,
    IncidentCommanderService,
    KnowledgeLearningService,
    OperationsCenterService,
    PredictiveReliabilityService,
    RCAEngineService,
    RemediationWorkflowService,
)
from app.schemas.sre import (
    AIRecommendationResponse,
    ChangeRiskRequest,
    CommanderResponse,
    CommanderStartRequest,
    ExecutiveAIReportRequest,
    LearnFromIncidentRequest,
    OperationsCenterResponse,
    PredictionResponse,
    RCAHypothesisResponse,
    RemediationWorkflowRequest,
    RunbookExecuteRequest,
    RunbookExecutionResponse,
)

router = APIRouter(prefix="/sre", tags=["Autonomous SRE"])

_ADMIN_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN}


def _org(ctx: OrgContext) -> str:
    return ctx.requires_organization


# --------------------------------------------------------------------------- #
# Incident Commander
# --------------------------------------------------------------------------- #
@router.post("/commander/start", response_model=CommanderResponse,
             status_code=status.HTTP_201_CREATED)
async def start_commander(body: CommanderStartRequest, session: DBSession, ctx: OrgContextDep):
    org_id = _org(ctx)
    commander = await IncidentCommanderService(session).start(
        organization_id=org_id, incident_id=body.incident_id, user_id=ctx.user.id)
    await session.commit()
    return commander


@router.get("/commander/{commander_id}", response_model=CommanderResponse)
async def get_commander(commander_id: str, session: DBSession, ctx: OrgContextDep):
    org_id = _org(ctx)
    row = await IncidentCommanderService(session).get(commander_id, organization_id=org_id)
    if row is None:
        raise HTTPException(status_code=404, detail="commander run not found")
    return row


@router.post("/commander/{commander_id}/approve", response_model=CommanderResponse)
async def approve_commander(commander_id: str, session: DBSession, ctx: OrgContextDep):
    org_id = _org(ctx)
    row = await IncidentCommanderService(session).approve(
        commander_id, organization_id=org_id, user_id=ctx.user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="commander run not found")
    await session.commit()
    return row


# --------------------------------------------------------------------------- #
# RCA
# --------------------------------------------------------------------------- #
@router.post("/rca/{incident_id}/analyze", response_model=list[RCAHypothesisResponse])
async def analyze_rca(incident_id: str, session: DBSession, ctx: OrgContextDep):
    org_id = _org(ctx)
    hypotheses = await RCAEngineService(session).analyze(
        organization_id=org_id, incident_id=incident_id)
    await session.commit()
    return hypotheses


@router.get("/rca/{incident_id}/hypotheses", response_model=list[RCAHypothesisResponse])
async def list_rca_hypotheses(incident_id: str, session: DBSession, ctx: OrgContextDep):
    org_id = _org(ctx)
    return await RCAEngineService(session).list_hypotheses(
        organization_id=org_id, incident_id=incident_id)


# --------------------------------------------------------------------------- #
# Executable runbooks
# --------------------------------------------------------------------------- #
@router.post("/runbooks/{runbook_id}/execute", response_model=RunbookExecutionResponse,
             status_code=status.HTTP_201_CREATED)
async def execute_runbook(
    runbook_id: str, body: RunbookExecuteRequest, session: DBSession, ctx: OrgContextDep,
):
    org_id = _org(ctx)
    try:
        execution = await ExecutableRunbookService(session).execute(
            organization_id=org_id, runbook_id=runbook_id,
            variables=body.variables, user_id=ctx.user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    await session.commit()
    return execution


@router.post("/runbooks/executions/{execution_id}/approve",
             response_model=RunbookExecutionResponse)
async def approve_runbook_execution(
    execution_id: str, session: DBSession, ctx: OrgContextDep,
):
    org_id = _org(ctx)
    ex = await ExecutableRunbookService(session).approve_execution(
        execution_id, organization_id=org_id, user_id=ctx.user.id)
    if ex is None:
        raise HTTPException(status_code=404, detail="execution not found")
    await session.commit()
    return ex


# --------------------------------------------------------------------------- #
# Remediation workflows
# --------------------------------------------------------------------------- #
@router.post("/remediation/workflows")
async def create_remediation_workflow(
    body: RemediationWorkflowRequest, session: DBSession, ctx: OrgContextDep,
):
    org_id = _org(ctx)
    result = await RemediationWorkflowService(session).create_workflow(
        organization_id=org_id, incident_id=body.incident_id,
        actions=body.actions, user_id=ctx.user.id)
    await session.commit()
    return result


# --------------------------------------------------------------------------- #
# Change risk
# --------------------------------------------------------------------------- #
@router.post("/change-risk/assess")
async def assess_change_risk(body: ChangeRiskRequest, session: DBSession, ctx: OrgContextDep):
    return await ChangeRiskEngineService(session).assess(
        ctx.user, ctx, candidate=body.model_dump())


# --------------------------------------------------------------------------- #
# Predictive reliability
# --------------------------------------------------------------------------- #
@router.post("/predictions/run", response_model=list[PredictionResponse])
async def run_predictions(session: DBSession, ctx: OrgContextDep,
                          target: str = Query("organization")):
    org_id = _org(ctx)
    preds = await PredictiveReliabilityService(session).predict_all(
        organization_id=org_id, target=target)
    await session.commit()
    return preds


# --------------------------------------------------------------------------- #
# AI Operations Center
# --------------------------------------------------------------------------- #
@router.get("/ops-center", response_model=OperationsCenterResponse)
async def ops_center(session: DBSession, ctx: OrgContextDep):
    org_id = _org(ctx)
    return await OperationsCenterService(session).dashboard(
        organization_id=org_id, user=ctx.user, org_context=ctx)


# --------------------------------------------------------------------------- #
# Executive AI reports
# --------------------------------------------------------------------------- #
@router.post("/reports/executive")
async def executive_ai_report(body: ExecutiveAIReportRequest, session: DBSession,
                              ctx: OrgContextDep):
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(status_code=403, detail="Admin required")
    return await ExecutiveAIReportService(session).generate(
        ctx.user, ctx, cadence=body.cadence)


# --------------------------------------------------------------------------- #
# Knowledge learning
# --------------------------------------------------------------------------- #
@router.post("/learning/capture")
async def capture_incident_knowledge(body: LearnFromIncidentRequest, session: DBSession,
                                     ctx: OrgContextDep):
    org_id = _org(ctx)
    stored = await KnowledgeLearningService(session).learn_from_incident(
        organization_id=org_id, incident_id=body.incident_id)
    await session.commit()
    return {"stored_memory_ids": stored}


# --------------------------------------------------------------------------- #
# Explainability
# --------------------------------------------------------------------------- #
@router.get("/recommendations/{resource_type}/{resource_id}",
            response_model=list[AIRecommendationResponse])
async def list_recommendations(resource_type: str, resource_id: str,
                               session: DBSession, ctx: OrgContextDep):
    org_id = _org(ctx)
    rows = list((await session.execute(
        select(SREAIRecommendation).where(
            SREAIRecommendation.organization_id == org_id,
            SREAIRecommendation.resource_type == resource_type,
            SREAIRecommendation.resource_id == resource_id,
        ).order_by(SREAIRecommendation.created_at.desc())
    )).scalars().all())
    svc = ExplainabilityService(session)
    return [svc.bundle(r) for r in rows]
