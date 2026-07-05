"""AI tools for the Platform Operator."""

from __future__ import annotations

from sqlalchemy import select

from app.ai.tools.runtime import Tool, ToolContext, ToolError, ToolKind, register_tool
from app.auth.org_context import OrgContext
from app.models.user import User
from app.repositories.organization import OrganizationMemberRepository
from app.services.ai_operator import AIOperatorService


async def _org_context(ctx: ToolContext) -> tuple[User, OrgContext]:
    if ctx.session is None or not ctx.organization_id or not ctx.user_id:
        raise ToolError("Organization and user context required")
    user = (await ctx.session.execute(select(User).where(User.id == ctx.user_id))).scalar_one_or_none()
    if user is None:
        raise ToolError("User not found", status_code=404)
    membership = await OrganizationMemberRepository(ctx.session).get_membership(
        ctx.organization_id, ctx.user_id,
    )
    if not user.is_superuser and membership is None:
        raise ToolError("Organization membership required", status_code=403)
    return user, OrgContext(user=user, organization_id=ctx.organization_id, role=membership.role if membership else None)


def _svc(ctx: ToolContext) -> AIOperatorService:
    return AIOperatorService(ctx.session)


async def _analyze(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    rows = await _svc(ctx).analyze(user, org, trigger=args.get("trigger", "ai_tool"))
    return {"created": len(rows), "recommendations": [
        {"id": r.id, "title": r.title, "kind": r.kind, "confidence": r.confidence}
        for r in rows[:10]
    ]}


async def _recommend(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    recs = await _svc(ctx).list_recommendations(user, org)
    pending = [r for r in recs if r.status == "PENDING"]
    return {"pending": len(pending), "items": [
        {"id": r.id, "title": r.title, "kind": r.kind, "impact": r.impact, "risk": r.risk}
        for r in pending[:10]
    ]}


async def _simulate(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    rec_id = args.get("recommendation_id")
    if not rec_id:
        recs = await _svc(ctx).list_recommendations(user, org)
        if not recs:
            return {"summary": "No recommendations to simulate."}
        rec_id = recs[0].id
    sim = await _svc(ctx).simulate(user, org, rec_id)
    return {"simulation_id": sim.id, "result": sim.result}


async def _execute_proposal(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    rec_id = args.get("recommendation_id")
    if not rec_id:
        raise ToolError("recommendation_id required")
    proposal = await _svc(ctx).propose_action(user, org, rec_id)
    if args.get("auto_approve"):
        proposal = await _svc(ctx).decide_proposal(user, org, proposal.id, approved=True)
    return {"proposal_id": proposal.id, "status": proposal.status}


def register_ai_operator_tools() -> None:
    register_tool(Tool(
        name="operator.analyze", kind=ToolKind.READ, handler=_analyze,
        description="Run continuous platform analysis and generate recommendations.",
        parameters={"type": "object", "properties": {"trigger": {"type": "string"}}},
    ))
    register_tool(Tool(
        name="operator.recommend", kind=ToolKind.READ, handler=_recommend,
        description="List pending operator recommendations with evidence.",
        parameters={"type": "object", "properties": {}},
    ))
    register_tool(Tool(
        name="operator.simulate", kind=ToolKind.READ, handler=_simulate,
        description="Simulate blast radius and impact for a recommendation.",
        parameters={
            "type": "object",
            "properties": {"recommendation_id": {"type": "string"}},
        },
    ))
    register_tool(Tool(
        name="operator.execute_proposal", kind=ToolKind.WRITE, handler=_execute_proposal,
        description="Propose and optionally approve an operator remediation action.",
        parameters={
            "type": "object",
            "properties": {
                "recommendation_id": {"type": "string"},
                "auto_approve": {"type": "boolean"},
            },
            "required": ["recommendation_id"],
        },
    ))


register_ai_operator_tools()
