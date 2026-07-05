"""AI Observability Engineer tools (Sprint 65B) — grounded evidence responses."""

from __future__ import annotations

from sqlalchemy import select

from app.ai.tools.runtime import Tool, ToolContext, ToolError, ToolKind, register_tool
from app.auth.org_context import OrgContext
from app.models.user import User
from app.repositories.organization import OrganizationMemberRepository
from app.services.observability_platform import ObservabilityPlatformService


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


def _svc(ctx: ToolContext) -> ObservabilityPlatformService:
    return ObservabilityPlatformService(ctx.session)


def _evidence(**parts) -> dict:
    return {"evidence": parts, "grounded": True}


async def _explain_metric(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    query = args.get("query") or args.get("metric")
    if not query:
        raise ToolError("query or metric required")
    result = await _svc(ctx).query_metrics(user, org, query=str(query), window=args.get("window", "1h"))
    try:
        from app.observability import metrics
        metrics.record_obs_ai_investigation("explain_metric")
    except Exception:  # noqa: BLE001
        pass
    return _evidence(
        query=query,
        result=result,
        explanation=f"Metric `{query}` sampled over {args.get('window', '1h')}.",
    )


async def _find_root_cause(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    service = args.get("service") or args.get("service_name")
    row = await _svc(ctx).correlate(
        user, org,
        title=args.get("title"),
        service_name=service,
        incident_id=args.get("incident_id"),
    )
    try:
        from app.observability import metrics
        metrics.record_obs_ai_investigation("find_root_cause")
    except Exception:  # noqa: BLE001
        pass
    return _evidence(
        timeline_id=row.id,
        root_cause=row.root_cause,
        timeline=row.timeline,
        summary=row.timeline.get("correlation_summary") if row.timeline else None,
    )


async def _trace_request(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    trace_id = args.get("trace_id") or args.get("query")
    if not trace_id:
        raise ToolError("trace_id or query required")
    result = await _svc(ctx).search_traces(user, org, query=str(trace_id), limit=5)
    try:
        from app.observability import metrics
        metrics.record_obs_ai_investigation("trace_request")
    except Exception:  # noqa: BLE001
        pass
    traces = result.get("traces", [])
    return _evidence(trace_id=trace_id, traces=traces[:3], total=result.get("total", 0))


async def _explain_logs(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    query = args.get("query") or "error"
    result = await _svc(ctx).search_logs(user, org, query=str(query), limit=int(args.get("limit", 20)))
    try:
        from app.observability import metrics
        metrics.record_obs_ai_investigation("explain_logs")
    except Exception:  # noqa: BLE001
        pass
    lines = result.get("lines", [])[:10]
    return _evidence(query=query, lines=lines, total=result.get("total", 0))


async def _detect_anomaly(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    query = args.get("query") or 'rate(http_requests_total{status=~"5.."}[5m])'
    metric = await _svc(ctx).query_metrics(user, org, query=str(query))
    alerts = await _svc(ctx).alert_intelligence(user, org)
    try:
        from app.observability import metrics
        metrics.record_obs_ai_investigation("detect_anomaly")
    except Exception:  # noqa: BLE001
        pass
    storms = alerts.get("storms", [])
    return _evidence(metric=metric, alert_storms=storms[:3], anomaly_detected=bool(storms))


async def _optimize_alerts(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    analysis = await _svc(ctx).alert_intelligence(user, org)
    try:
        from app.observability import metrics
        metrics.record_obs_ai_investigation("optimize_alerts")
    except Exception:  # noqa: BLE001
        pass
    return _evidence(
        groups=analysis.get("groups", [])[:5],
        recommendations=analysis.get("recommendations", []),
        storms=analysis.get("storms", []),
    )


async def _suggest_slo(ctx: ToolContext, args: dict):
    user, org = await _org_context(ctx)
    dash = await _svc(ctx).slo_dashboard(user, org)
    try:
        from app.observability import metrics
        metrics.record_obs_ai_investigation("suggest_slo")
    except Exception:  # noqa: BLE001
        pass
    services = dash.get("services", [])
    suggestions = []
    for svc in services[:5]:
        score = svc.get("health_score", 100)
        target = 99.9 if score > 80 else 99.5
        suggestions.append({
            "service_id": svc.get("id"),
            "service_name": svc.get("name"),
            "suggested_availability_target": target,
            "rationale": "Based on current health score and error budget posture",
        })
    return _evidence(services=services[:5], suggestions=suggestions)


def register_observability_tools() -> None:
    register_tool(Tool(
        name="observability.explain_metric",
        description="Explain a metric query with grounded time-series evidence.",
        kind=ToolKind.READ,
        parameters={"type": "object", "properties": {
            "query": {"type": "string"}, "metric": {"type": "string"}, "window": {"type": "string"},
        }},
        handler=_explain_metric,
    ))
    register_tool(Tool(
        name="observability.find_root_cause",
        description="Correlate logs, metrics, traces, and alerts to find root cause.",
        kind=ToolKind.READ,
        parameters={"type": "object", "properties": {
            "service": {"type": "string"}, "service_name": {"type": "string"},
            "incident_id": {"type": "string"}, "title": {"type": "string"},
        }},
        handler=_find_root_cause,
    ))
    register_tool(Tool(
        name="observability.trace_request",
        description="Search distributed traces for a request or trace ID.",
        kind=ToolKind.READ,
        parameters={"type": "object", "properties": {
            "trace_id": {"type": "string"}, "query": {"type": "string"},
        }},
        handler=_trace_request,
    ))
    register_tool(Tool(
        name="observability.explain_logs",
        description="Search and explain log patterns with evidence lines.",
        kind=ToolKind.READ,
        parameters={"type": "object", "properties": {
            "query": {"type": "string"}, "limit": {"type": "integer"},
        }},
        handler=_explain_logs,
    ))
    register_tool(Tool(
        name="observability.detect_anomaly",
        description="Detect metric and alert anomalies using live signals.",
        kind=ToolKind.READ,
        parameters={"type": "object", "properties": {"query": {"type": "string"}}},
        handler=_detect_anomaly,
    ))
    register_tool(Tool(
        name="observability.optimize_alerts",
        description="Recommend alert grouping, suppression, and threshold tuning.",
        kind=ToolKind.READ,
        parameters={"type": "object", "properties": {}},
        handler=_optimize_alerts,
    ))
    register_tool(Tool(
        name="observability.suggest_slo",
        description="Suggest SLO targets based on service health and error budgets.",
        kind=ToolKind.READ,
        parameters={"type": "object", "properties": {}},
        handler=_suggest_slo,
    ))


register_observability_tools()
