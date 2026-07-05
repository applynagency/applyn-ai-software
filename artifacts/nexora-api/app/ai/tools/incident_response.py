"""AI Incident Coordinator tools (Sprint 65C) — grounded evidence responses."""

from __future__ import annotations

from sqlalchemy import select

from app.ai.tools.runtime import Tool, ToolContext, ToolError, ToolKind, register_tool
from app.auth.org_context import OrgContext
from app.models.user import User
from app.repositories.organization import OrganizationMemberRepository
from app.schemas.incident_response import CommunicationCreate
from app.services.incident_response import IncidentResponsePlatformService


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


def _svc(ctx: ToolContext) -> IncidentResponsePlatformService:
    return IncidentResponsePlatformService(ctx.session)


def _evidence(**parts) -> dict:
    return {"evidence": parts, "grounded": True}


async def _find_best_responder(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    row = await _svc(ctx).coordinate(user, org, incident_id=args.get("incident_id"))
    return _evidence(
        coordinator_run_id=row.id,
        recommended_responders=row.result.get("recommended_responders", []),
        recommended_severity=row.result.get("recommended_severity"),
    )


async def _summarize(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    incident_id = args.get("incident_id")
    if not incident_id:
        raise ToolError("incident_id required")
    analytics = await _svc(ctx).analytics(user, org)
    comms = await _svc(ctx).list_communications(user, org, incident_id=incident_id)
    return _evidence(
        incident_id=incident_id,
        open_incidents=analytics.get("open_incidents"),
        communications=[{"subject": c.subject, "kind": c.kind} for c in comms[:3]],
    )


async def _generate_status_update(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    row = await _svc(ctx).create_communication(
        user, org,
        CommunicationCreate(
            incident_id=args.get("incident_id"),
            template_key=args.get("template_key", "incident_status_customer"),
            context={
                "title": args.get("title", "Incident"),
                "status": args.get("status", "Investigating"),
                "severity": args.get("severity", "MEDIUM"),
            },
        ),
    )
    return _evidence(communication_id=row.id, subject=row.subject, body=row.body[:500])


async def _predict_severity(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    row = await _svc(ctx).coordinate(user, org, incident_id=args.get("incident_id"))
    return _evidence(
        severity=row.result.get("recommended_severity"),
        impact=row.result.get("predicted_impact"),
        groups=row.result.get("groups", [])[:3],
    )


async def _generate_postmortem(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    incident_id = args.get("incident_id")
    if not incident_id:
        raise ToolError("incident_id required")
    pm = await _svc(ctx).generate_postmortem(user, org, incident_id)
    return _evidence(postmortem_id=pm.id, title=pm.title, status=pm.status)


async def _explain_timeline(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    row = await _svc(ctx).coordinate(user, org, incident_id=args.get("incident_id"))
    return _evidence(
        timeline_draft=row.result.get("timeline_draft", []),
        postmortem_outline=row.result.get("postmortem_outline"),
    )


async def _suggest_actions(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    row = await _svc(ctx).coordinate(user, org, incident_id=args.get("incident_id"))
    return _evidence(
        suggested_rollback=row.result.get("suggested_rollback"),
        suggested_communications=row.result.get("suggested_communications", []),
        recommended_responders=row.result.get("recommended_responders", []),
    )


def register_incident_response_tools() -> None:
    tools = [
        ("incident.find_best_responder", "Find best on-call responder with evidence.", _find_best_responder, {"incident_id": {"type": "string"}}),
        ("incident.summarize", "Summarize incident state and communications.", _summarize, {"incident_id": {"type": "string"}}),
        ("incident.generate_status_update", "Generate customer-safe status update.", _generate_status_update, {"incident_id": {"type": "string"}, "title": {"type": "string"}}),
        ("incident.predict_severity", "Predict severity from live signals.", _predict_severity, {"incident_id": {"type": "string"}}),
        ("incident.generate_postmortem", "Generate postmortem draft from incident data.", _generate_postmortem, {"incident_id": {"type": "string"}}),
        ("incident.explain_timeline", "Explain incident timeline from correlated events.", _explain_timeline, {"incident_id": {"type": "string"}}),
        ("incident.suggest_actions", "Suggest rollback and response actions.", _suggest_actions, {"incident_id": {"type": "string"}}),
    ]
    for name, desc, handler, props in tools:
        register_tool(Tool(
            name=name, description=desc, kind=ToolKind.READ,
            parameters={"type": "object", "properties": props},
            handler=handler,
        ))


register_incident_response_tools()
