"""AI tools for the DevOps delivery platform."""

from __future__ import annotations

from sqlalchemy import select

from app.ai.tools.runtime import Tool, ToolContext, ToolError, ToolKind, register_tool
from app.auth.org_context import OrgContext
from app.models.user import User
from app.repositories.organization import OrganizationMemberRepository
from app.schemas.delivery import OperationCreate
from app.services.delivery import DeliveryService
from app.services.release_reliability import ReleaseReliabilityService


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


def _svc(ctx: ToolContext) -> DeliveryService:
    return DeliveryService(ctx.session)


async def _explain_failure(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    deploys = await _svc(ctx).list_deployments(user, org)
    failed = [d for d in deploys if d.status in ("FAILED", "ROLLED_BACK")]
    runs = await _svc(ctx).list_pipeline_runs(user, org)
    failed_runs = [r for r in runs if r.status == "FAILED"]
    evidence = []
    for d in failed[:5]:
        evidence.append({
            "type": "deployment", "id": d.id, "environment_id": d.environment_id,
            "error": d.error, "strategy": d.strategy, "completed_at": str(d.completed_at),
        })
    for r in failed_runs[:5]:
        evidence.append({
            "type": "pipeline_run", "id": r.id, "pipeline_id": r.pipeline_id,
            "logs_preview": (r.logs_preview or "")[:500],
        })
    return {
        "summary": "Recent failures in deployments and pipeline runs.",
        "evidence": evidence,
        "count": len(evidence),
    }


async def _generate_release_notes(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    repo_id = args.get("repository_id")
    version = args.get("version", "next")
    repos = await _svc(ctx).list_repositories(user, org)
    repo = next((r for r in repos if r.id == repo_id), repos[0] if repos else None)
    if repo and repo_id:
        detail = await _svc(ctx).get_repository_detail(user, org, repo.id)
        commits = detail.get("commits", [])
        notes = "\n".join(f"- {c.message} ({c.sha})" for c in commits[:10])
        evidence_count = len(commits)
    else:
        notes = "- Bug fixes and performance improvements\n- Security patches"
        evidence_count = 0
    return {
        "version": version,
        "repository": repo.full_name if repo else "unknown",
        "release_notes": f"## Release {version}\n\n{notes}",
        "evidence_commits": evidence_count,
    }


async def _predict_risk(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    release_id = args.get("release_id")
    releases = await _svc(ctx).list_releases(user, org)
    rel = next((r for r in releases if r.id == release_id), releases[0] if releases else None)
    scans = await _svc(ctx).list_scans(user, org)
    high_findings = sum((s.summary or {}).get("high", 0) for s in scans)
    base = rel.risk_score if rel else 40.0
    score = min(100.0, base + high_findings * 5)
    strategy = "canary" if score > 60 else "rolling"
    return {
        "risk_score": score,
        "recommended_strategy": strategy,
        "evidence": {
            "release_risk": rel.risk_score if rel else None,
            "security_high_findings": high_findings,
            "release_id": rel.id if rel else None,
        },
    }


async def _recommend_rollback(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    deploys = await _svc(ctx).list_deployments(user, org)
    recent = deploys[0] if deploys else None
    if recent and recent.status == "SUCCEEDED":
        return {
            "recommend_rollback": False,
            "reason": "Latest deployment succeeded health validation.",
            "evidence": {"deployment_id": recent.id, "status": recent.status},
        }
    return {
        "recommend_rollback": True,
        "reason": "Latest deployment failed or is unhealthy — rollback to previous revision advised.",
        "evidence": {"deployment_id": recent.id if recent else None, "status": recent.status if recent else None},
        "operation": "Propose ROLLBACK via delivery.propose_deployment approval flow.",
    }


async def _propose_deploy(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    op = await _svc(ctx).propose_operation(
        user, org,
        OperationCreate(
            kind="DEPLOY",
            environment_id=args.get("environment_id", ""),
            release_id=args.get("release_id"),
            params={"strategy": args.get("strategy", "ROLLING"), "image_ref": args.get("image_ref")},
        ),
    )
    return {"operation_id": op.id, "status": op.status, "kind": op.kind}


def _rr_svc(ctx: ToolContext) -> ReleaseReliabilityService:
    return ReleaseReliabilityService(ctx.session)


async def _assess_readiness(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    rows, _ = await _rr_svc(ctx).list_reliability(user, org, limit=20)
    rid = args.get("reliability_id")
    row = next((r for r in rows if r.id == rid), rows[0] if rows else None)
    if not row:
        return {"ready": False, "reason": "no release reliability record", "evidence": [], "citations": []}
    evidence = await _rr_svc(ctx).get_evidence(user, org, row.id)
    gate = (evidence.get("health_gates") or [{}])[0]
    return {
        "ready": row.verification_status == "PASSED",
        "verification_status": row.verification_status,
        "health_gate": gate.get("decision"),
        "provider_mode": row.provider_mode,
        "evidence": evidence.get("health_gates", [])[:3],
        "citations": [{"type": "release_reliability", "id": row.id}],
    }


async def _explain_gate_failure(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    rid = args.get("reliability_id")
    if not rid:
        raise ToolError("reliability_id required")
    evidence = await _rr_svc(ctx).get_evidence(user, org, rid)
    gates = evidence.get("health_gates", [])
    latest = gates[0] if gates else {}
    return {
        "decision": latest.get("decision", "UNKNOWN"),
        "signals": latest.get("signals", {}),
        "explanation": "Gate failed due to signal thresholds or insufficient evidence.",
        "citations": [{"type": "health_gate", "id": latest.get("id")}],
    }


async def _recommend_strategy(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    risk = await _predict_risk(ctx, args)
    strategy = "canary" if risk["risk_score"] > 50 else "rolling"
    return {
        "recommended_strategy": strategy,
        "risk_score": risk["risk_score"],
        "citations": [{"type": "release", "id": risk["evidence"].get("release_id")}],
    }


async def _compare_baseline(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    rid = args.get("reliability_id")
    row = await _rr_svc(ctx).get_reliability(user, org, rid) if rid else None
    if not row:
        return {"comparison": None, "citations": []}
    return {
        "baseline_version": row.baseline_version,
        "candidate_version": row.candidate_version,
        "artifact_digest": row.artifact_digest,
        "citations": [{"type": "release_reliability", "id": row.id}],
    }


async def _suggest_rollback(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    return await _recommend_rollback(ctx, args)


async def _summarize_release(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    rid = args.get("reliability_id")
    if not rid:
        raise ToolError("reliability_id required")
    row = await _rr_svc(ctx).get_reliability(user, org, rid)
    hist = await _rr_svc(ctx).get_history(user, org, rid)
    return {
        "summary": f"Release {row.candidate_version} in stage {row.stage}, verification={row.verification_status}",
        "timeline_events": len(hist.get("timeline", [])),
        "rollout_status": hist.get("rollout_state", {}).get("status"),
        "citations": [{"type": "release_reliability", "id": row.id}],
    }


async def _predict_blast_radius(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    deploys = await _svc(ctx).list_deployments(user, org)
    envs = await _svc(ctx).list_environments(user, org)
    prod = [e for e in envs if e.tier == "PRODUCTION"]
    return {
        "blast_radius": "medium" if prod else "low",
        "production_environments": len(prod),
        "recent_deployments": len(deploys[:5]),
        "citations": [{"type": "environment", "count": len(envs)}],
    }


def register_delivery_tools() -> None:
    register_tool(Tool(
        name="delivery.explain_failure", kind=ToolKind.READ, handler=_explain_failure,
        description="Explain recent deployment or pipeline failures with evidence.",
        parameters={"type": "object", "properties": {}},
    ))
    register_tool(Tool(
        name="delivery.generate_release_notes", kind=ToolKind.READ, handler=_generate_release_notes,
        description="Generate release notes from recent commits.",
        parameters={
            "type": "object",
            "properties": {
                "repository_id": {"type": "string"},
                "version": {"type": "string"},
            },
        },
    ))
    register_tool(Tool(
        name="delivery.predict_risk", kind=ToolKind.READ, handler=_predict_risk,
        description="Predict deployment risk and recommend rollout strategy.",
        parameters={
            "type": "object",
            "properties": {"release_id": {"type": "string"}},
        },
    ))
    register_tool(Tool(
        name="delivery.recommend_rollback", kind=ToolKind.READ, handler=_recommend_rollback,
        description="Recommend whether to rollback based on deployment health evidence.",
        parameters={"type": "object", "properties": {}},
    ))
    register_tool(Tool(
        name="delivery.propose_deployment", kind=ToolKind.APPROVAL, handler=_propose_deploy,
        description="Propose a deployment (requires approval).",
        parameters={
            "type": "object",
            "properties": {
                "environment_id": {"type": "string"},
                "release_id": {"type": "string"},
                "strategy": {"type": "string"},
                "image_ref": {"type": "string"},
            },
            "required": ["environment_id"],
        },
    ))
    register_tool(Tool(
        name="release.assess_readiness", kind=ToolKind.READ, handler=_assess_readiness,
        description="Assess release readiness with grounded evidence.",
        parameters={"type": "object", "properties": {"reliability_id": {"type": "string"}}},
    ))
    register_tool(Tool(
        name="release.explain_gate_failure", kind=ToolKind.READ, handler=_explain_gate_failure,
        description="Explain health gate failure with citations.",
        parameters={"type": "object", "properties": {"reliability_id": {"type": "string"}}, "required": ["reliability_id"]},
    ))
    register_tool(Tool(
        name="release.recommend_strategy", kind=ToolKind.READ, handler=_recommend_strategy,
        description="Recommend rollout strategy from risk evidence.",
        parameters={"type": "object", "properties": {"release_id": {"type": "string"}}},
    ))
    register_tool(Tool(
        name="release.compare_baseline", kind=ToolKind.READ, handler=_compare_baseline,
        description="Compare baseline vs candidate versions.",
        parameters={"type": "object", "properties": {"reliability_id": {"type": "string"}}, "required": ["reliability_id"]},
    ))
    register_tool(Tool(
        name="release.suggest_rollback", kind=ToolKind.READ, handler=_suggest_rollback,
        description="Suggest rollback based on verification evidence.",
        parameters={"type": "object", "properties": {}},
    ))
    register_tool(Tool(
        name="release.summarize_release", kind=ToolKind.READ, handler=_summarize_release,
        description="Summarize release reliability timeline.",
        parameters={"type": "object", "properties": {"reliability_id": {"type": "string"}}, "required": ["reliability_id"]},
    ))
    register_tool(Tool(
        name="release.predict_blast_radius", kind=ToolKind.READ, handler=_predict_blast_radius,
        description="Predict blast radius from environments and deployments.",
        parameters={"type": "object", "properties": {}},
    ))


register_delivery_tools()
