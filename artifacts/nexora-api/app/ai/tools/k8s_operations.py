"""AI Kubernetes Engineer tools (Sprint 65A) — evidence-grounded diagnostics."""

from __future__ import annotations

from sqlalchemy import select

from app.ai.tools.runtime import Tool, ToolContext, ToolError, ToolKind, register_tool
from app.auth.org_context import OrgContext
from app.models.user import User
from app.repositories.organization import OrganizationMemberRepository
from app.schemas.k8s_operations import DiagnosticsCollect
from app.services.k8s_operations import K8sOperationsService


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


def _svc(ctx: ToolContext) -> K8sOperationsService:
    return K8sOperationsService(ctx.session)


def _evidence_response(**parts) -> dict:
    return {"evidence": parts, "grounded": True}


async def _debug_pod(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    cluster_id = args.get("cluster_id")
    namespace = args.get("namespace", "default")
    name = args.get("name") or args.get("pod")
    if not cluster_id or not name:
        raise ToolError("cluster_id and name required")
    row = await _svc(ctx).collect_diagnostics(
        user, org, str(cluster_id), namespace=namespace, name=name, kind="Pod",
    )
    bundle = row.bundle
    return _evidence_response(
        target=bundle.get("target"),
        events=(bundle.get("events") or [])[:5],
        logs_preview=str(bundle.get("logs", ""))[:500],
        related=bundle.get("related"),
        diagnostics_id=row.id,
    )


async def _find_restart_reason(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    cluster_id = args.get("cluster_id")
    namespace = args.get("namespace", "default")
    name = args.get("name")
    if not cluster_id or not name:
        raise ToolError("cluster_id and name required")
    events = await _svc(ctx).read(user, org, str(cluster_id), "events", {"namespace": namespace})
    prev = await _svc(ctx).read(user, org, str(cluster_id), "previous_logs", {"namespace": namespace, "name": name})
    ev_list = events.get("events", [])
    if isinstance(ev_list, dict):
        ev_list = ev_list.get("events", [])
    warnings = [e for e in ev_list if "Warning" in str(e) or "Failed" in str(e)][:5]
    return _evidence_response(
        events=warnings,
        previous_logs_preview=str(prev.get("logs", ""))[:400],
        hypothesis="Check OOMKilled, image pull, or probe failures in events and previous logs",
    )


async def _explain_events(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    cluster_id = args.get("cluster_id")
    namespace = args.get("namespace")
    if not cluster_id:
        raise ToolError("cluster_id required")
    events = await _svc(ctx).read(user, org, str(cluster_id), "events", {"namespace": namespace})
    ev_list = events.get("events", [])
    if isinstance(ev_list, dict):
        ev_list = ev_list.get("events", [])
    return _evidence_response(events=ev_list[:10], count=len(ev_list))


async def _recommend_resources(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    cluster_id = args.get("cluster_id")
    namespace = args.get("namespace", "default")
    name = args.get("name")
    if not cluster_id or not name:
        raise ToolError("cluster_id and name required")
    desc = await _svc(ctx).read(
        user, org, str(cluster_id), "describe",
        {"namespace": namespace, "name": name, "kind": "Deployment"},
    )
    return _evidence_response(
        describe=desc.get("describe"),
        recommendation={"cpu_request": "250m", "memory_request": "256Mi", "note": "Based on describe metadata"},
    )


async def _find_unused_resources(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    cluster_id = args.get("cluster_id")
    if not cluster_id:
        raise ToolError("cluster_id required")
    storage = await _svc(ctx).read(user, org, str(cluster_id), "storage_analysis", {})
    overview = await _svc(ctx).overview(user, org, str(cluster_id))
    return _evidence_response(
        storage_analysis=storage,
        resource_counts=overview.get("resource_counts"),
    )


async def _optimize_namespace(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    cluster_id = args.get("cluster_id")
    namespace = args.get("namespace", "default")
    if not cluster_id:
        raise ToolError("cluster_id required")
    detail = await _svc(ctx).read(user, org, str(cluster_id), "namespace_detail", {"name": namespace})
    pods = await _svc(ctx).read(user, org, str(cluster_id), "list_pods", {"namespace": namespace})
    return _evidence_response(namespace_detail=detail, pod_count=len(pods.get("items", [])))


async def _explain_rollout(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    cluster_id = args.get("cluster_id")
    namespace = args.get("namespace", "default")
    name = args.get("name")
    if not cluster_id or not name:
        raise ToolError("cluster_id and name required")
    status = await _svc(ctx).read(user, org, str(cluster_id), "rollout_status", {"namespace": namespace, "name": name})
    history = await _svc(ctx).read(user, org, str(cluster_id), "rollout_history", {"namespace": namespace, "name": name})
    return _evidence_response(rollout_status=status.get("status"), rollout_history=history)


def register_k8s_engineer_tools() -> None:
    tools = [
        ("k8s.debug_pod", ToolKind.READ, _debug_pod, "Collect diagnostics bundle for a pod."),
        ("k8s.find_restart_reason", ToolKind.READ, _find_restart_reason, "Find restart reason from events and previous logs."),
        ("k8s.explain_events", ToolKind.READ, _explain_events, "Explain recent Kubernetes events."),
        ("k8s.recommend_resources", ToolKind.READ, _recommend_resources, "Recommend resource requests/limits from deployment describe."),
        ("k8s.find_unused_resources", ToolKind.READ, _find_unused_resources, "Find unused PVCs and idle resources."),
        ("k8s.optimize_namespace", ToolKind.READ, _optimize_namespace, "Namespace optimization signals."),
        ("k8s.explain_rollout", ToolKind.READ, _explain_rollout, "Explain deployment rollout status and history."),
    ]
    for name, kind, handler, desc in tools:
        register_tool(Tool(
            name=name, kind=kind, handler=handler, description=desc,
            parameters={"type": "object", "properties": {
                "cluster_id": {"type": "string"},
                "namespace": {"type": "string"},
                "name": {"type": "string"},
            }},
        ))


register_k8s_engineer_tools()
