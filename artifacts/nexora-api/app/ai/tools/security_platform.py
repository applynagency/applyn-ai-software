"""AI Security Engineer tools (Sprint 65D) — grounded, redacted evidence."""

from __future__ import annotations

from sqlalchemy import select

from app.ai.tools.runtime import Tool, ToolContext, ToolError, ToolKind, register_tool
from app.auth.org_context import OrgContext
from app.models.user import User
from app.repositories.organization import OrganizationMemberRepository
from app.schemas.security_platform import RemediationProposalCreate, ScanRequest
from app.services.security_platform import SecurityPlatformService


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


def _svc(ctx: ToolContext) -> SecurityPlatformService:
    return SecurityPlatformService(ctx.session)


def _evidence(**parts) -> dict:
    return {"evidence": parts, "grounded": True, "citations": list(parts.keys())}


async def _explain_finding(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    finding_id = args.get("finding_id")
    if not finding_id:
        raise ToolError("finding_id required")
    rows, _ = await _svc(ctx).list_findings(user, org, limit=200)
    row = next((r for r in rows if r.id == finding_id), None)
    if not row:
        raise ToolError("Finding not found", status_code=404)
    return _evidence(
        finding_id=row.id, title=row.title, severity=row.severity, source=row.source,
        cve=row.cve, remediation=row.remediation_guidance,
        evidence=row.evidence,
    )


async def _prioritize_risks(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    data = await _svc(ctx).analytics(user, org)
    rows, _ = await _svc(ctx).list_findings(user, org, severity="CRITICAL", limit=10)
    return _evidence(
        posture=data, critical_findings=[{"id": r.id, "title": r.title} for r in rows],
    )


async def _find_attack_surface(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    k8s = await _svc(ctx).kubernetes_security(user, org)
    cloud = await _svc(ctx).cloud_posture(user, org)
    return _evidence(kubernetes=k8s, cloud=cloud)


async def _explain_cve_impact(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    cve = args.get("cve")
    rows, _ = await _svc(ctx).list_findings(user, org, limit=100)
    matched = [r for r in rows if r.cve == cve or (cve and cve in (r.title or ""))]
    return _evidence(cve=cve, findings=[{"title": r.title, "severity": r.severity, "resource": r.resource} for r in matched[:5]])


async def _recommend_remediation(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    finding_id = args.get("finding_id")
    if not finding_id:
        raise ToolError("finding_id required")
    row = await _svc(ctx).propose_remediation(
        user, org,
        RemediationProposalCreate(
            finding_id=finding_id,
            kind=args.get("kind", "NOTIFY_OWNER"),
            title=args.get("title", "Recommended remediation"),
            rollback_plan=args.get("rollback_plan"),
        ),
    )
    return _evidence(proposal_id=row.id, kind=row.kind, requires_approval=True, status=row.status)


async def _review_iac_plan(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    target = args.get("target", "terraform/main.tf")
    scan = await _svc(ctx).run_scan(user, org, ScanRequest(kind="IAC", target=target))
    return _evidence(scan_id=scan.id, simulated=scan.simulated, summary=scan.summary, gate=scan.gate_decision)


async def _analyze_rbac(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    data = await _svc(ctx).identity_security(user, org)
    scan = await _svc(ctx).run_scan(user, org, ScanRequest(kind="IAM", target=args.get("target", "org")))
    return _evidence(identity=data, scan_summary=scan.summary)


async def _generate_exception_justification(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    finding_id = args.get("finding_id")
    rows, _ = await _svc(ctx).list_findings(user, org, limit=50)
    row = next((r for r in rows if r.id == finding_id), None)
    if not row:
        raise ToolError("Finding not found", status_code=404)
    return _evidence(
        finding_id=row.id, severity=row.severity, title=row.title,
        suggested_justification=f"Accepted risk for {row.title} with compensating controls and expiry review",
    )


def register_security_tools() -> None:
    tools = [
        ("security.explain_finding", "Explain a security finding with evidence.", _explain_finding, {"finding_id": {"type": "string"}}),
        ("security.prioritize_risks", "Prioritize risks by severity and posture.", _prioritize_risks, {}),
        ("security.find_attack_surface", "Map Kubernetes and cloud attack surface.", _find_attack_surface, {}),
        ("security.explain_cve_impact", "Explain CVE impact from org findings.", _explain_cve_impact, {"cve": {"type": "string"}}),
        ("security.recommend_remediation", "Create approval-gated remediation proposal.", _recommend_remediation, {"finding_id": {"type": "string"}, "kind": {"type": "string"}}),
        ("security.review_iac_plan", "Review IaC plan for policy violations.", _review_iac_plan, {"target": {"type": "string"}}),
        ("security.analyze_rbac", "Analyze IAM/RBAC posture.", _analyze_rbac, {"target": {"type": "string"}}),
        ("security.generate_exception_justification", "Draft risk exception justification.", _generate_exception_justification, {"finding_id": {"type": "string"}}),
    ]
    for name, desc, handler, props in tools:
        register_tool(Tool(
            name=name, description=desc, kind=ToolKind.READ,
            parameters={"type": "object", "properties": props},
            handler=handler,
        ))


register_security_tools()
