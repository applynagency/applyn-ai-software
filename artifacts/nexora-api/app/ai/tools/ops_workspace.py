"""AI tools for the DevOps & SRE workspace."""

from __future__ import annotations

from sqlalchemy import select

from app.ai.tools.runtime import Tool, ToolContext, ToolError, ToolKind, register_tool
from app.auth.org_context import OrgContext
from app.models.user import User
from app.repositories.organization import OrganizationMemberRepository
from app.services.devops_sre_workspace import DevOpsSREWorkspaceService


async def _org_context(ctx: ToolContext) -> tuple[User, OrgContext]:
    if ctx.session is None or not ctx.organization_id or not ctx.user_id:
        raise ToolError("Organization and user context required")
    user = (
        await ctx.session.execute(select(User).where(User.id == ctx.user_id))
    ).scalar_one_or_none()
    if user is None:
        raise ToolError("User not found", status_code=404)
    membership = await OrganizationMemberRepository(ctx.session).get_membership(
        ctx.organization_id, ctx.user_id,
    )
    if not user.is_superuser and membership is None:
        raise ToolError("Organization membership required", status_code=403)
    role = membership.role if membership else None
    return user, OrgContext(user=user, organization_id=ctx.organization_id, role=role)


def _svc(ctx: ToolContext) -> DevOpsSREWorkspaceService:
    return DevOpsSREWorkspaceService(ctx.session)


async def _my_work(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    return await _svc(ctx).my_work(user, org)


async def _queue(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    data = await _svc(ctx).queue(user, org)
    return {"total": data["total"], "items": data["items"][:10]}


async def _generate_briefing(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    row = await _svc(ctx).generate_daily_briefing(user, org)
    return {"id": row.id, "summary": row.summary, "date": row.briefing_date}


async def _generate_handover(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    row = await _svc(ctx).generate_handover(user, org)
    return {"id": row.id, "title": row.title, "markdown_preview": row.markdown[:500]}


async def _ai_context(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    return await _svc(ctx).ai_context(
        user, org,
        page=args.get("page"),
        reference_type=args.get("reference_type"),
        reference_id=args.get("reference_id"),
        question=args.get("question"),
    )


async def _explain_queue_item(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    data = await _svc(ctx).queue(user, org)
    item_id = args.get("item_id")
    item = next((i for i in data["items"] if i["id"] == item_id), data["items"][0] if data["items"] else None)
    if not item:
        return {"summary": "Operations queue is empty."}
    return {
        "item": item,
        "explanation": f"{item['title']} is {item['status']} with {item['priority']} priority. "
                       f"Suggested action: {item['suggested_action']}",
    }


def register_ops_workspace_tools() -> None:
    register_tool(Tool(
        name="ops_workspace.my_work", kind=ToolKind.READ, handler=_my_work,
        description="Get the personalized My Work dashboard for the current engineer.",
        parameters={"type": "object", "properties": {}},
    ))
    register_tool(Tool(
        name="ops_workspace.queue", kind=ToolKind.READ, handler=_queue,
        description="List the unified operations queue (incidents, alerts, deployments, approvals).",
        parameters={"type": "object", "properties": {}},
    ))
    register_tool(Tool(
        name="ops_workspace.generate_briefing", kind=ToolKind.WRITE, handler=_generate_briefing,
        description="Generate the AI daily operations briefing and store it in the activity feed.",
        parameters={"type": "object", "properties": {}},
    ))
    register_tool(Tool(
        name="ops_workspace.generate_handover", kind=ToolKind.WRITE, handler=_generate_handover,
        description="Generate a shift handover document with platform state and pending work.",
        parameters={"type": "object", "properties": {}},
    ))
    register_tool(Tool(
        name="ops_workspace.ai_context", kind=ToolKind.READ, handler=_ai_context,
        description="Build grounded AI side-panel context for a page or resource.",
        parameters={
            "type": "object",
            "properties": {
                "page": {"type": "string"},
                "reference_type": {"type": "string"},
                "reference_id": {"type": "string"},
                "question": {"type": "string"},
            },
        },
    ))
    register_tool(Tool(
        name="ops_workspace.explain_queue_item", kind=ToolKind.READ, handler=_explain_queue_item,
        description="Explain a queue item and recommend next steps.",
        parameters={
            "type": "object",
            "properties": {"item_id": {"type": "string"}},
        },
    ))


register_ops_workspace_tools()
