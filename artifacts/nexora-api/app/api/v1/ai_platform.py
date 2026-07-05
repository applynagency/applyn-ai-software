"""AI Platform API (Sprint 61D).

One surface for the unified AI runtime: generation through the gateway, provider
& routing config, prompt registry, tool runtime, agent runtime, long-term
memory, MCP servers, evaluations, cost reporting and the playground.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.ai.agent_runtime import AgentRuntime, AgentRuntimeError
from app.ai.cost import CostTracker
from app.ai.evaluation import AIEvaluator
from app.ai.gateway import AIGateway, AIGatewayError
from app.ai.mcp import MCPError, MCPServerService, local_mcp_manifest
from app.ai.memory import MemoryService
from app.ai.playground import PlaygroundService
from app.ai.prompts import PromptError, PromptRegistry
from app.ai.provider_config import ProviderConfigError, ProviderConfigService
from app.ai.providers import available_providers, get_provider
from app.ai.tools import ToolContext, ToolRuntime
from app.ai.types import LLMMessage, LLMRequest
from app.auth.dependencies import DBSession
from app.auth.org_context import OrgContext, OrgContextDep
from app.models.organization import OrganizationRole
from app.schemas.ai_platform import (
    AgentRunResponse,
    AgentStartRequest,
    CompletionRequest,
    CompletionResponse,
    EvaluationResponse,
    MCPServerCreate,
    MCPServerResponse,
    MemoryEntryResponse,
    MemoryRecallRequest,
    MemoryWriteRequest,
    PlaygroundModelsRequest,
    PlaygroundPromptRequest,
    PlaygroundProvidersRequest,
    PlaygroundTempsRequest,
    PromptCreate,
    PromptListResponse,
    PromptRenderRequest,
    PromptResponse,
    PromptRollbackRequest,
    ProviderInfo,
    ProvidersResponse,
    RoutingConfigResponse,
    RoutingConfigUpdate,
    ToolExecuteRequest,
    ToolSpecResponse,
)

router = APIRouter(prefix="/ai", tags=["AI Platform"])

_ADMIN_ROLES = {OrganizationRole.OWNER, OrganizationRole.ADMIN}


def _require_org_admin(ctx: OrgContext) -> str:
    org_id = ctx.requires_organization
    if not (ctx.user.is_superuser or ctx.role in _ADMIN_ROLES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Organization admin role required")
    return org_id


# --- providers & routing ----------------------------------------------------


@router.get("/providers", response_model=ProvidersResponse)
async def list_providers(ctx: OrgContextDep):
    _ = ctx.requires_organization
    items = [
        ProviderInfo(name=name, configured=get_provider(name).is_configured(),
                     default_model=get_provider(name).default_model)
        for name in available_providers()
    ]
    return ProvidersResponse(items=items, total=len(items))


@router.get("/routing", response_model=RoutingConfigResponse)
async def get_routing(session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    config = await ProviderConfigService(session).get(org_id)
    if config is None:
        from app.core.config import settings

        return RoutingConfigResponse(
            routing_policy=settings.AI_PLATFORM_DEFAULT_ROUTING,
            enabled_providers=None, preferred_models=None,
            default_temperature=0.2, default_max_tokens=1024, cache_enabled=True,
        )
    return RoutingConfigResponse.model_validate(config)


@router.put("/routing", response_model=RoutingConfigResponse)
async def update_routing(body: RoutingConfigUpdate, session: DBSession, ctx: OrgContextDep):
    org_id = _require_org_admin(ctx)
    try:
        config = await ProviderConfigService(session).upsert(
            organization_id=org_id, actor_user_id=ctx.user.id,
            **body.model_dump(exclude_none=True))
    except ProviderConfigError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return RoutingConfigResponse.model_validate(config)


# --- generation -------------------------------------------------------------


@router.post("/complete", response_model=CompletionResponse)
async def complete(body: CompletionRequest, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    req = LLMRequest(
        messages=[LLMMessage(role="user", content=body.prompt)], system=body.system,
        provider=body.provider, model=body.model, temperature=body.temperature,
        max_tokens=body.max_tokens, feature=body.feature, organization_id=org_id,
        user_id=ctx.user.id,
    )
    try:
        resp = await AIGateway(session).complete(req)
    except AIGatewayError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    await session.commit()
    return CompletionResponse(
        text=resp.text, provider=resp.provider, model=resp.model, mode=resp.mode,
        usage=resp.usage.as_dict(), cost_usd=round(resp.cost_usd, 6),
        cached=resp.cached, latency_ms=round(resp.latency_ms, 2),
    )


@router.post("/stream")
async def stream(body: CompletionRequest, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    req = LLMRequest(
        messages=[LLMMessage(role="user", content=body.prompt)], system=body.system,
        provider=body.provider, model=body.model, temperature=body.temperature,
        max_tokens=body.max_tokens, feature=body.feature, organization_id=org_id,
        user_id=ctx.user.id,
    )

    async def _gen():
        async for chunk in AIGateway(session).stream(req):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


# --- prompts ----------------------------------------------------------------


@router.post("/prompts", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt(body: PromptCreate, session: DBSession, ctx: OrgContextDep):
    org_id = _require_org_admin(ctx)
    scope_org = org_id if body.organization_scope else None
    if scope_org is None and not ctx.user.is_superuser:
        raise HTTPException(status_code=403, detail="Global prompts require superuser")
    try:
        tmpl = await PromptRegistry(session).register(
            key=body.key, template=body.template, organization_id=scope_org,
            variables=body.variables, description=body.description,
            actor_user_id=ctx.user.id)
    except PromptError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return PromptResponse.model_validate(tmpl)


@router.get("/prompts/{key}", response_model=PromptResponse)
async def get_prompt(key: str, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    tmpl = await PromptRegistry(session).get_active(key, org_id)
    if tmpl is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return PromptResponse.model_validate(tmpl)


@router.get("/prompts/{key}/versions", response_model=PromptListResponse)
async def list_prompt_versions(key: str, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    versions = await PromptRegistry(session).list_versions(key, org_id)
    return PromptListResponse(
        items=[PromptResponse.model_validate(v) for v in versions], total=len(versions))


@router.post("/prompts/{key}/render")
async def render_prompt(key: str, body: PromptRenderRequest, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    try:
        text = await PromptRegistry(session).render(key, body.variables, organization_id=org_id)
    except PromptError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    return {"key": key, "rendered": text}


@router.post("/prompts/{key}/rollback", response_model=PromptResponse)
async def rollback_prompt(key: str, body: PromptRollbackRequest, session: DBSession, ctx: OrgContextDep):
    org_id = _require_org_admin(ctx)
    try:
        tmpl = await PromptRegistry(session).rollback(
            key, body.version, organization_id=org_id, actor_user_id=ctx.user.id)
    except PromptError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return PromptResponse.model_validate(tmpl)


# --- tools ------------------------------------------------------------------


@router.get("/tools", response_model=list[ToolSpecResponse])
async def list_tools(ctx: OrgContextDep):
    _ = ctx.requires_organization
    ctx_obj = ToolContext()
    return [ToolSpecResponse(**spec) for spec in ToolRuntime(ctx_obj).list_tools()]


@router.post("/tools/{name}/execute")
async def execute_tool(name: str, body: ToolExecuteRequest, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    tool_ctx = ToolContext(session=session, organization_id=org_id, user_id=ctx.user.id)
    result = await ToolRuntime(tool_ctx).execute(name, body.args, approved=body.approved)
    await session.commit()
    if result.approval_required:
        raise HTTPException(status_code=status.HTTP_202_ACCEPTED, detail="approval_required")
    return result.as_dict()


# --- agents -----------------------------------------------------------------


@router.post("/agents", response_model=AgentRunResponse, status_code=status.HTTP_201_CREATED)
async def start_agent(body: AgentStartRequest, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    run = await AgentRuntime(session).start(
        organization_id=org_id, agent_key=body.agent_key, goal=body.goal,
        user_id=ctx.user.id, steps=body.steps)
    await session.commit()
    return AgentRunResponse.model_validate(run)


@router.get("/agents/{run_id}", response_model=AgentRunResponse)
async def get_agent_run(run_id: str, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    run = await AgentRuntime(session).get(org_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return AgentRunResponse.model_validate(run)


@router.post("/agents/{run_id}/run", response_model=AgentRunResponse)
async def run_agent(run_id: str, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    try:
        run = await AgentRuntime(session).run_to_completion(org_id, run_id)
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return AgentRunResponse.model_validate(run)


@router.post("/agents/{run_id}/approve", response_model=AgentRunResponse)
async def approve_agent(run_id: str, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    try:
        run = await AgentRuntime(session).approve(org_id, run_id, actor_user_id=ctx.user.id)
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return AgentRunResponse.model_validate(run)


@router.post("/agents/{run_id}/cancel", response_model=AgentRunResponse)
async def cancel_agent(run_id: str, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    try:
        run = await AgentRuntime(session).cancel(org_id, run_id, actor_user_id=ctx.user.id)
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return AgentRunResponse.model_validate(run)


@router.post("/agents/{run_id}/resume", response_model=AgentRunResponse)
async def resume_agent(run_id: str, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    try:
        run = await AgentRuntime(session).resume(org_id, run_id)
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return AgentRunResponse.model_validate(run)


# --- memory -----------------------------------------------------------------


@router.post("/memory", response_model=MemoryEntryResponse, status_code=status.HTTP_201_CREATED)
async def write_memory(body: MemoryWriteRequest, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    entry = await MemoryService(session).remember(
        organization_id=org_id, content=body.content, scope=body.scope,
        namespace=body.namespace, user_id=ctx.user.id, importance=body.importance,
        metadata=body.metadata)
    await session.commit()
    try:
        from app.observability import metrics

        metrics.record_ai_memory(body.scope)
    except Exception:  # pragma: no cover
        pass
    return MemoryEntryResponse.model_validate(entry)


@router.post("/memory/recall")
async def recall_memory(body: MemoryRecallRequest, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    results = await MemoryService(session).recall(
        organization_id=org_id, query=body.query, scope=body.scope,
        namespace=body.namespace, top_k=body.top_k)
    return {"results": results, "total": len(results)}


@router.get("/memory", response_model=list[MemoryEntryResponse])
async def list_memory(session: DBSession, ctx: OrgContextDep, scope: str | None = None):
    org_id = ctx.requires_organization
    entries = await MemoryService(session).list_entries(organization_id=org_id, scope=scope)
    return [MemoryEntryResponse.model_validate(e) for e in entries]


# --- mcp --------------------------------------------------------------------


@router.get("/mcp/manifest")
async def mcp_manifest(ctx: OrgContextDep):
    _ = ctx.requires_organization
    return local_mcp_manifest()


@router.get("/mcp/servers", response_model=list[MCPServerResponse])
async def list_mcp_servers(session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    servers = await MCPServerService(session).list_servers(org_id)
    return [MCPServerResponse.model_validate(s) for s in servers]


@router.post("/mcp/servers", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def register_mcp_server(body: MCPServerCreate, session: DBSession, ctx: OrgContextDep):
    org_id = _require_org_admin(ctx)
    try:
        server = await MCPServerService(session).register(
            organization_id=org_id, name=body.name, url=body.url,
            transport=body.transport, auth_token=body.auth_token,
            actor_user_id=ctx.user.id)
    except MCPError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return MCPServerResponse.model_validate(server)


@router.delete("/mcp/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deregister_mcp_server(server_id: str, session: DBSession, ctx: OrgContextDep):
    org_id = _require_org_admin(ctx)
    ok = await MCPServerService(session).deregister(org_id, server_id, actor_user_id=ctx.user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="MCP server not found")
    await session.commit()


@router.post("/mcp/servers/{server_id}/sync")
async def sync_mcp_server(server_id: str, session: DBSession, ctx: OrgContextDep):
    org_id = _require_org_admin(ctx)
    try:
        tools = await MCPServerService(session).sync_tools(org_id, server_id)
    except MCPError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from None
    await session.commit()
    return {"tools": tools, "total": len(tools)}


# --- evaluation & cost ------------------------------------------------------


@router.get("/evaluations", response_model=list[EvaluationResponse])
async def list_evaluations(session: DBSession, ctx: OrgContextDep, feature: str | None = None):
    org_id = ctx.requires_organization
    items = await AIEvaluator(session).history(org_id, feature=feature)
    return [EvaluationResponse.model_validate(e) for e in items]


@router.get("/evaluations/summary")
async def evaluation_summary(session: DBSession, ctx: OrgContextDep, days: int = 30):
    org_id = ctx.requires_organization
    return await AIEvaluator(session).aggregate(org_id, days=days)


@router.get("/cost")
async def cost_report(session: DBSession, ctx: OrgContextDep, days: int = 30, by_feature: bool = False):
    org_id = ctx.requires_organization
    return await CostTracker(session).summary(org_id, days=days, by_feature=by_feature)


# --- playground -------------------------------------------------------------


@router.post("/playground/prompt")
async def playground_prompt(body: PlaygroundPromptRequest, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    result = await PlaygroundService(session).test_prompt(
        prompt=body.prompt, system=body.system, provider=body.provider,
        model=body.model, temperature=body.temperature, organization_id=org_id)
    await session.commit()
    return result


@router.post("/playground/models")
async def playground_models(body: PlaygroundModelsRequest, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    results = await PlaygroundService(session).compare_models(
        prompt=body.prompt, models=body.models, system=body.system,
        temperature=body.temperature, organization_id=org_id)
    await session.commit()
    return {"results": results}


@router.post("/playground/temperatures")
async def playground_temperatures(body: PlaygroundTempsRequest, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    results = await PlaygroundService(session).compare_temperatures(
        prompt=body.prompt, temperatures=body.temperatures, provider=body.provider,
        model=body.model, system=body.system, organization_id=org_id)
    await session.commit()
    return {"results": results}


@router.post("/playground/providers")
async def playground_providers(body: PlaygroundProvidersRequest, session: DBSession, ctx: OrgContextDep):
    org_id = ctx.requires_organization
    results = await PlaygroundService(session).compare_providers(
        prompt=body.prompt, providers=body.providers, system=body.system,
        temperature=body.temperature, organization_id=org_id)
    await session.commit()
    return {"results": results}
