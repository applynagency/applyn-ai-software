"""AI tools for Platform Engineering."""

from __future__ import annotations

from sqlalchemy import select

from app.ai.tools.runtime import Tool, ToolContext, ToolError, ToolKind, register_tool
from app.auth.org_context import OrgContext
from app.models.user import User
from app.repositories.organization import OrganizationMemberRepository
from app.schemas.platform_engineering import IaCRunCreate, IaCStackCreate, ProvisionCreate
from app.services.platform_engineering import PlatformEngineeringService


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


def _svc(ctx: ToolContext) -> PlatformEngineeringService:
    return PlatformEngineeringService(ctx.session)


async def _generate_terraform(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    stack = await _svc(ctx).create_stack(user, org, IaCStackCreate(
        name=args.get("name", "generated-stack"),
        provider=args.get("provider", "TERRAFORM"),
        variables=args.get("variables", {"region": "us-east-1"}),
    ))
    run = await _svc(ctx).propose_run(user, org, stack.id, IaCRunCreate(kind="PLAN"))
    return {"stack_id": stack.id, "run_id": run.id, "status": run.status}


async def _explain_plan(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    runs = await _svc(ctx).list_runs(user, org)
    run = next((r for r in runs if r.id == args.get("run_id")), runs[0] if runs else None)
    if not run:
        return {"summary": "No Terraform runs found."}
    return {
        "run_id": run.id,
        "kind": run.kind,
        "plan_summary": run.plan_summary,
        "explanation": f"Plan {run.kind}: {run.plan_summary or 'no summary'}",
    }


async def _find_drift(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    findings = await _svc(ctx).scan_drift(user, org)
    return {"count": len(findings), "findings": [
        {"source": f.source, "resource": f.resource, "message": f.message, "ai": f.ai_explanation}
        for f in findings[:10]
    ]}


async def _provision_cluster(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    prov = await _svc(ctx).start_provision(user, org, ProvisionCreate(
        template_kind=args.get("template_kind", "EKS"),
        distribution=args.get("distribution", "EKS"),
    ))
    return {"provision_id": prov.id, "status": prov.status, "note": "Requires approval before execution"}


def register_platform_engineering_tools() -> None:
    register_tool(Tool(
        name="pe.generate_terraform", kind=ToolKind.WRITE, handler=_generate_terraform,
        description="Generate a Terraform stack and run plan.",
        parameters={"type": "object", "properties": {"name": {"type": "string"}, "provider": {"type": "string"}}},
    ))
    register_tool(Tool(
        name="pe.explain_plan", kind=ToolKind.READ, handler=_explain_plan,
        description="Explain a Terraform plan.",
        parameters={"type": "object", "properties": {"run_id": {"type": "string"}}},
    ))
    register_tool(Tool(
        name="pe.find_drift", kind=ToolKind.READ, handler=_find_drift,
        description="Scan and explain infrastructure drift.",
        parameters={"type": "object", "properties": {}},
    ))
    register_tool(Tool(
        name="pe.provision_cluster", kind=ToolKind.APPROVAL, handler=_provision_cluster,
        description="Propose cluster provisioning (requires approval).",
        parameters={
            "type": "object",
            "properties": {"distribution": {"type": "string"}, "template_kind": {"type": "string"}},
        },
    ))


register_platform_engineering_tools()
