"""Control plane AI tools — cluster-aware read and approval-gated mutations."""

from __future__ import annotations

from sqlalchemy import select

from app.ai.tools.runtime import Tool, ToolContext, ToolError, ToolKind, register_tool
from app.auth.org_context import OrgContext
from app.models.user import User
from app.repositories.organization import OrganizationMemberRepository
from app.schemas.control_plane import OperationCreate
from app.services.control_plane import ControlPlaneService


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


def _svc(ctx: ToolContext) -> ControlPlaneService:
    return ControlPlaneService(ctx.session)


async def _list_clusters(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    rows = await _svc(ctx).list_clusters(user, org)
    return {
        "clusters": [
            {
                "id": c.id, "name": c.name, "distribution": c.distribution,
                "health": c.health, "node_count": c.node_count,
                "namespace_count": c.namespace_count,
            }
            for c in rows
        ],
    }


async def _discover_cluster(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    cluster_id = args.get("cluster_id")
    if not cluster_id:
        raise ToolError("cluster_id is required")
    run = await _svc(ctx).discover_cluster(user, org, str(cluster_id))
    return {"discovery_run_id": run.id, "status": run.status, "resource_count": run.resource_count}


async def _list_unhealthy_pods(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    cluster_id = args.get("cluster_id")
    namespace = args.get("namespace")
    clusters = await _svc(ctx).list_clusters(user, org)
    if cluster_id:
        targets = [c for c in clusters if c.id == cluster_id]
        if not targets:
            raise ToolError("Cluster not found", status_code=404)
    else:
        targets = clusters
    unhealthy: list[dict] = []
    for cluster in targets:
        resources = await _svc(ctx).list_cluster_resources(
            user, org, cluster.id, kind="Pod", namespace=namespace,
        )
        for res in resources:
            if res.health not in ("HEALTHY",):
                unhealthy.append({
                    "cluster_id": cluster.id, "cluster": cluster.name,
                    "namespace": res.namespace, "name": res.name,
                    "health": res.health, "labels": res.labels or {},
                })
    return {"unhealthy_pods": unhealthy, "count": len(unhealthy)}


async def _propose_k8s_operation(ctx: ToolContext, args: dict, *, kind: str):
    user, org = await _org_context(ctx)
    cluster_id = args.get("cluster_id")
    if not cluster_id:
        raise ToolError("cluster_id is required")
    payload = OperationCreate(
        kind=kind,
        cluster_id=str(cluster_id),
        namespace=args.get("namespace"),
        resource_name=args.get("resource_name") or args.get("name"),
        params=args.get("params") or {},
    )
    if kind == "SCALE_DEPLOYMENT" and "replicas" in args:
        payload.params = {**payload.params, "replicas": args["replicas"]}
    op = await _svc(ctx).propose_operation(user, org, payload)
    return {
        "operation_id": op.id, "status": op.status, "kind": op.kind,
        "message": "Operation proposed — approve and execute via /v1/control-plane/operations",
    }


async def _scale_deployment(ctx: ToolContext, args: dict):
    return await _propose_k8s_operation(ctx, args, kind="SCALE_DEPLOYMENT")


async def _restart_deployment(ctx: ToolContext, args: dict):
    return await _propose_k8s_operation(ctx, args, kind="RESTART_DEPLOYMENT")


def register_control_plane_tools() -> None:
    register_tool(Tool(
        name="control_plane.list_clusters", kind=ToolKind.READ, handler=_list_clusters,
        description="List Kubernetes clusters registered for the organization.",
        parameters={"type": "object", "properties": {}},
    ))
    register_tool(Tool(
        name="control_plane.discover_cluster", kind=ToolKind.WRITE, handler=_discover_cluster,
        description="Run live cluster discovery to refresh namespaces, workloads, and resources.",
        parameters={
            "type": "object",
            "properties": {"cluster_id": {"type": "string"}},
            "required": ["cluster_id"],
        },
    ))
    register_tool(Tool(
        name="k8s.list_unhealthy_pods", kind=ToolKind.READ, handler=_list_unhealthy_pods,
        description="List pods that are not healthy across one or all clusters.",
        parameters={
            "type": "object",
            "properties": {
                "cluster_id": {"type": "string"},
                "namespace": {"type": "string"},
            },
        },
    ))
    register_tool(Tool(
        name="k8s.scale_deployment", kind=ToolKind.APPROVAL, handler=_scale_deployment,
        description="Propose scaling a deployment (requires approval before execution).",
        parameters={
            "type": "object",
            "properties": {
                "cluster_id": {"type": "string"},
                "namespace": {"type": "string"},
                "resource_name": {"type": "string"},
                "replicas": {"type": "integer"},
            },
            "required": ["cluster_id", "namespace", "resource_name", "replicas"],
        },
    ))
    register_tool(Tool(
        name="k8s.restart_deployment", kind=ToolKind.APPROVAL, handler=_restart_deployment,
        description="Propose restarting a deployment (requires approval before execution).",
        parameters={
            "type": "object",
            "properties": {
                "cluster_id": {"type": "string"},
                "namespace": {"type": "string"},
                "resource_name": {"type": "string"},
            },
            "required": ["cluster_id", "namespace", "resource_name"],
        },
    ))


register_control_plane_tools()
