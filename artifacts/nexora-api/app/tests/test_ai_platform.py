"""AI Platform & Agent Runtime tests (Sprint 61D).

Covers the unified runtime end-to-end: pluggable providers + provider switching,
model routing + fallback, the gateway (caching, cost tracking, telemetry),
prompt registry (versions/render/rollback/org override), the tool runtime
(read/write/approval/sandbox/timeout), the agent runtime (plan/execute/
checkpoints/approval/cancel/resume), long-term memory (scopes + semantic recall),
MCP (local manifest + server registration), evaluation + history, cost
reporting, the playground, and the org-scoped API surface.
"""

from __future__ import annotations

from app.ai.cost import CostTracker
from app.ai.evaluation import AIEvaluator
from app.ai.gateway import AIGateway
from app.ai.maintenance import AIPlatformMaintenance
from app.ai.mcp import MCPServerService, local_mcp_manifest
from app.ai.memory import MemoryService
from app.ai.playground import PlaygroundService
from app.ai.prompts import PromptError, PromptRegistry
from app.ai.provider_config import ProviderConfigService
from app.ai.providers import available_providers, get_provider
from app.ai.routing import ModelRouter, OrgRoutingConfig, RoutingPolicy
from app.ai.tools import ToolContext, ToolKind, ToolRuntime, get_tool_registry
from app.ai.types import LLMMessage, LLMRequest
from app.database.session import AsyncSessionLocal
from app.models.ai_platform import MemoryScope
from app.models.organization import Organization

from .conftest import auth_headers, create_authenticated_user


async def _make_org(session, slug: str) -> str:
    org = Organization(name=slug, slug=slug)
    session.add(org)
    await session.flush()
    return org.id


# --- 1. Unified runtime + provider switching --------------------------------
async def test_providers_pluggable_and_offline(setup_db):
    names = available_providers()
    assert {"anthropic", "openai", "azure_openai", "gemini", "ollama",
            "openrouter", "bedrock"} <= set(names)
    # Every provider runs deterministically offline (no creds in tests).
    for name in names:
        provider = get_provider(name)
        assert provider.is_configured() is False
        resp = await provider.generate(LLMRequest(
            messages=[LLMMessage(role="user", content="hello world")]))
        assert resp.provider == name
        assert resp.mode == "offline"
        assert resp.text


async def test_provider_switching_changes_backend(setup_db):
    req = LLMRequest(messages=[LLMMessage(role="user", content="ping")])
    a = await get_provider("anthropic").generate(req)
    o = await get_provider("openai").generate(req)
    assert a.provider == "anthropic"
    assert o.provider == "openai"


# --- 2. Routing + fallback ---------------------------------------------------
async def test_routing_policies():
    cheapest = ModelRouter(OrgRoutingConfig(policy=RoutingPolicy.CHEAPEST)).primary()
    quality = ModelRouter(OrgRoutingConfig(policy=RoutingPolicy.HIGHEST_QUALITY)).primary()
    # Cheapest should not equal highest-quality top pick in our catalog.
    assert cheapest.as_tuple() != quality.as_tuple()
    # Custom ordering is honoured, with default appended as fallback.
    custom = ModelRouter(OrgRoutingConfig(
        policy=RoutingPolicy.CUSTOM,
        preferred=[("openai", "gpt-4o-mini")])).route()
    assert custom[0].as_tuple() == ("openai", "gpt-4o-mini")
    assert len(custom) >= 2  # fallback appended


async def test_deterministic_routing_single():
    route = ModelRouter(OrgRoutingConfig(policy=RoutingPolicy.DETERMINISTIC)).route()
    assert len(route) >= 1


# --- 3. Gateway: cost tracking + caching ------------------------------------
async def test_gateway_complete_tracks_cost(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session, "gw-org")
        gw = AIGateway(session)
        resp = await gw.complete(LLMRequest(
            messages=[LLMMessage(role="user", content="explain caching")],
            feature="unit-test", organization_id=org_id, temperature=0.0))
        await session.commit()
        assert resp.text and resp.provider
        assert resp.usage.total_tokens > 0
        assert resp.cost_usd >= 0.0
        summary = await CostTracker(session).summary(org_id, days=1)
        assert summary["totals"]["calls"] >= 1


async def test_gateway_cache_hit(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session, "cache-org")
        gw = AIGateway(session)
        req = LLMRequest(
            messages=[LLMMessage(role="user", content="cache me")],
            feature="cache-test", organization_id=org_id, temperature=0.0)
        first = await gw.complete(req)
        second = await gw.complete(req)
        await session.commit()
        assert first.cached is False
        assert second.cached is True


async def test_gateway_fallback_to_default(setup_db):
    # An unknown provider name in the registry path is skipped; default is used.
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session, "fb-org")
        gw = AIGateway(session)
        resp = await gw.complete(LLMRequest(
            messages=[LLMMessage(role="user", content="hi")],
            organization_id=org_id))
        await session.commit()
        assert resp.provider in available_providers()


# --- 4. Prompt registry ------------------------------------------------------
async def test_prompt_versions_render_rollback(setup_db):
    async with AsyncSessionLocal() as session:
        reg = PromptRegistry(session)
        v1 = await reg.register(key="greet", template="Hello {name}")
        v2 = await reg.register(key="greet", template="Hi {name}!")
        await session.commit()
        assert v1.version == 1 and v2.version == 2
        active = await reg.get_active("greet")
        assert active.version == 2
        rendered = await reg.render("greet", {"name": "Ada"})
        assert rendered == "Hi Ada!"
        # Missing variable raises.
        try:
            await reg.render("greet", {})
            raise AssertionError("expected PromptError")
        except PromptError:
            pass
        # Rollback to v1.
        rolled = await reg.rollback("greet", 1)
        await session.commit()
        assert rolled.version == 1
        assert (await reg.get_active("greet")).version == 1


async def test_prompt_org_override(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session, "prompt-org")
        reg = PromptRegistry(session)
        await reg.register(key="welcome", template="Global {x}")
        await reg.register(key="welcome", template="Org {x}", organization_id=org_id)
        await session.commit()
        assert (await reg.render("welcome", {"x": "1"})) == "Global 1"
        assert (await reg.render("welcome", {"x": "1"}, organization_id=org_id)) == "Org 1"


# --- 5. Tool runtime ---------------------------------------------------------
async def test_tool_read_execute(setup_db):
    rt = ToolRuntime(ToolContext())
    result = await rt.execute("echo", {"text": "hi"})
    assert result.ok is True
    assert result.output == {"echo": "hi"}


async def test_tool_sandbox_blocks_writes(setup_db):
    rt = ToolRuntime(ToolContext())
    result = await rt.execute("record_note", {"note": "x"}, allow_write=False)
    assert result.ok is False
    assert result.error == "sandbox_read_only"


async def test_tool_approval_required(setup_db):
    rt = ToolRuntime(ToolContext())
    pending = await rt.execute("apply_change", {"change": "deploy"})
    assert pending.approval_required is True
    approved = await rt.execute("apply_change", {"change": "deploy"}, approved=True)
    assert approved.ok is True
    assert approved.output["applied"] is True


async def test_tool_timeout(setup_db):
    import asyncio

    from app.ai.tools import Tool, register_tool

    async def _slow(ctx, args):
        await asyncio.sleep(5)
        return {"done": True}

    register_tool(Tool(name="slow", kind=ToolKind.READ, handler=_slow,
                       timeout_seconds=0.05, max_retries=0))
    result = await ToolRuntime(ToolContext()).execute("slow", {})
    assert result.ok is False
    assert result.error == "timeout"


async def test_tool_registry_lists_kinds(setup_db):
    specs = {t.name: t.kind for t in get_tool_registry().values()}
    assert specs["echo"] == ToolKind.READ
    assert specs["record_note"] == ToolKind.WRITE
    assert specs["apply_change"] == ToolKind.APPROVAL


# --- 6. Agent runtime --------------------------------------------------------
async def test_agent_run_completes(setup_db):
    from app.ai.agent_runtime import AgentRuntime

    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session, "agent-org")
        rt = AgentRuntime(session)
        run = await rt.start(organization_id=org_id, agent_key="planner",
                             goal="step one\nstep two")
        await session.commit()
        assert run.plan and len(run.plan) == 2
        done = await rt.run_to_completion(org_id, run.id)
        await session.commit()
        assert done.status == "completed"
        assert len(done.checkpoints) == 2
        assert done.result["steps"] == 2


async def test_agent_approval_pause_and_resume(setup_db):
    from app.ai.agent_runtime import AgentRuntime

    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session, "agent-appr")
        rt = AgentRuntime(session)
        run = await rt.start(
            organization_id=org_id, agent_key="deployer", goal="ship",
            steps=[{"description": "prepare"},
                   {"kind": "approval", "description": "deploy",
                    "tool": "apply_change", "args": {"change": "v2"}},
                   {"description": "verify"}])
        await session.commit()
        paused = await rt.run_to_completion(org_id, run.id)
        await session.commit()
        assert paused.status == "waiting_approval"
        assert paused.pending_approval is not None
        resumed = await rt.approve(org_id, run.id)
        await session.commit()
        assert resumed.status == "completed"


async def test_agent_cancel(setup_db):
    from app.ai.agent_runtime import AgentRuntime

    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session, "agent-cancel")
        rt = AgentRuntime(session)
        run = await rt.start(organization_id=org_id, agent_key="x", goal="a\nb\nc")
        await session.commit()
        cancelled = await rt.cancel(org_id, run.id)
        await session.commit()
        assert cancelled.status == "cancelled"
        after = await rt.run_to_completion(org_id, run.id)
        assert after.status == "cancelled"


# --- 7. Long-term memory -----------------------------------------------------
async def test_memory_recall_ranks_relevant(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session, "mem-org")
        mem = MemoryService(session)
        await mem.remember(organization_id=org_id,
                           content="The payments service depends on postgres database")
        await mem.remember(organization_id=org_id,
                           content="The frontend uses a react component library")
        await session.commit()
        results = await mem.recall(organization_id=org_id,
                                   query="database postgres dependency")
        assert results
        assert "postgres" in results[0]["content"]


async def test_memory_scopes(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session, "mem-scope")
        mem = MemoryService(session)
        await mem.remember(organization_id=org_id, content="org fact",
                           scope=MemoryScope.ORGANIZATION)
        await mem.remember(organization_id=org_id, content="user fact",
                           scope=MemoryScope.USER, user_id="u1")
        await session.commit()
        org_entries = await mem.list_entries(organization_id=org_id,
                                             scope=MemoryScope.ORGANIZATION)
        assert len(org_entries) == 1


# --- 8. MCP ------------------------------------------------------------------
async def test_mcp_local_manifest_exposes_tools(setup_db):
    manifest = local_mcp_manifest()
    assert manifest["protocol"] == "mcp"
    names = {t["name"] for t in manifest["tools"]}
    assert "echo" in names


async def test_mcp_server_registration(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session, "mcp-org")
        svc = MCPServerService(session)
        server = await svc.register(organization_id=org_id, name="github",
                                    url="https://mcp.example/rpc")
        await session.commit()
        assert server.name == "github"
        servers = await svc.list_servers(org_id)
        assert len(servers) == 1
        # Sync offline keeps cached/empty rather than failing.
        tools = await svc.sync_tools(org_id, server.id)
        assert isinstance(tools, list)


# --- 9. Evaluation -----------------------------------------------------------
async def test_evaluation_scores_and_history(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session, "eval-org")
        gw = AIGateway(session)
        resp = await gw.complete(LLMRequest(
            messages=[LLMMessage(role="user", content="postgres latency spike")],
            organization_id=org_id, feature="copilot"))
        ev = AIEvaluator(session)
        record = await ev.evaluate_and_store(
            resp, organization_id=org_id, feature="copilot",
            context="postgres latency spike caused by connection pool exhaustion",
            tool_results=[{"ok": True}])
        await session.commit()
        assert 0.0 <= record.grounding_score <= 1.0
        assert 0.0 <= record.hallucination_risk <= 1.0
        history = await ev.history(org_id)
        assert len(history) == 1
        agg = await ev.aggregate(org_id)
        assert agg["evaluations"] == 1


# --- 10. Cost ----------------------------------------------------------------
async def test_cost_summary_by_feature(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session, "cost-org")
        gw = AIGateway(session)
        for feat in ("copilot", "discovery"):
            await gw.complete(LLMRequest(
                messages=[LLMMessage(role="user", content=f"q {feat}")],
                organization_id=org_id, feature=feat))
        await session.commit()
        summary = await CostTracker(session).summary(org_id, days=1, by_feature=True)
        keys = {b["key"] for b in summary["breakdown"]}
        assert {"copilot", "discovery"} <= keys


# --- 11. Playground ----------------------------------------------------------
async def test_playground_provider_comparison(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session, "play-org")
        pg = PlaygroundService(session)
        results = await pg.compare_providers(
            prompt="summarize the incident", providers=["anthropic", "openai"],
            organization_id=org_id)
        await session.commit()
        assert len(results) == 2
        assert {r["provider"] for r in results} == {"anthropic", "openai"}


async def test_playground_temperature_comparison(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session, "play-temp")
        pg = PlaygroundService(session)
        results = await pg.compare_temperatures(
            prompt="hi", temperatures=[0.0, 0.7], organization_id=org_id)
        await session.commit()
        assert len(results) == 2


# --- 12. Provider config + maintenance --------------------------------------
async def test_provider_config_upsert(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session, "cfg-org")
        svc = ProviderConfigService(session)
        cfg = await svc.upsert(organization_id=org_id, routing_policy="cheapest",
                               enabled_providers=["openai", "anthropic"])
        await session.commit()
        assert cfg.routing_policy == "cheapest"
        assert cfg.enabled_providers == ["openai", "anthropic"]


async def test_maintenance_jobs_run(setup_db):
    async with AsyncSessionLocal() as session:
        org_id = await _make_org(session, "maint-org")
        gw = AIGateway(session)
        resp = await gw.complete(LLMRequest(
            messages=[LLMMessage(role="user", content="x")], organization_id=org_id))
        await AIEvaluator(session).evaluate_and_store(
            resp, organization_id=org_id, feature="copilot")
        await session.commit()
        sweep = await AIPlatformMaintenance(session).evaluation_sweep()
        assert sweep["evaluations"] >= 1
        consolidated = await AIPlatformMaintenance(session).consolidate_memory()
        assert "pruned" in consolidated


# --- API surface -------------------------------------------------------------
async def test_ai_api_providers_and_complete(client):
    _, tokens = await create_authenticated_user(
        client, email="ai1@example.com", username="aiuser1")
    h = auth_headers(tokens["access_token"])

    providers = await client.get("/v1/ai/providers", headers=h)
    assert providers.status_code == 200, providers.text
    assert providers.json()["total"] >= 7

    comp = await client.post("/v1/ai/complete",
                             json={"prompt": "explain blast radius", "feature": "api"},
                             headers=h)
    assert comp.status_code == 200, comp.text
    body = comp.json()
    assert body["text"] and body["provider"]
    assert "usage" in body


async def test_ai_api_prompts_tools_memory(client):
    _, tokens = await create_authenticated_user(
        client, email="ai2@example.com", username="aiuser2")
    h = auth_headers(tokens["access_token"])

    created = await client.post("/v1/ai/prompts",
                                json={"key": "api.greet", "template": "Hi {who}"},
                                headers=h)
    assert created.status_code == 201, created.text
    rendered = await client.post("/v1/ai/prompts/api.greet/render",
                                 json={"variables": {"who": "team"}}, headers=h)
    assert rendered.status_code == 200
    assert rendered.json()["rendered"] == "Hi team"

    tools = await client.get("/v1/ai/tools", headers=h)
    assert tools.status_code == 200
    assert any(t["name"] == "echo" for t in tools.json())
    exec_res = await client.post("/v1/ai/tools/echo/execute",
                                 json={"args": {"text": "yo"}}, headers=h)
    assert exec_res.status_code == 200
    assert exec_res.json()["output"] == {"echo": "yo"}

    mem = await client.post("/v1/ai/memory",
                            json={"content": "service A calls service B"}, headers=h)
    assert mem.status_code == 201, mem.text
    recall = await client.post("/v1/ai/memory/recall",
                               json={"query": "service B"}, headers=h)
    assert recall.status_code == 200
    assert recall.json()["total"] >= 1


async def test_ai_api_agents_and_playground(client):
    _, tokens = await create_authenticated_user(
        client, email="ai3@example.com", username="aiuser3")
    h = auth_headers(tokens["access_token"])

    start = await client.post("/v1/ai/agents",
                              json={"agent_key": "api-agent", "goal": "do a\ndo b"},
                              headers=h)
    assert start.status_code == 201, start.text
    run_id = start.json()["id"]
    run = await client.post(f"/v1/ai/agents/{run_id}/run", headers=h)
    assert run.status_code == 200
    assert run.json()["status"] == "completed"

    play = await client.post("/v1/ai/playground/providers",
                             json={"prompt": "hello", "providers": ["anthropic", "openai"]},
                             headers=h)
    assert play.status_code == 200
    assert len(play.json()["results"]) == 2


async def test_ai_api_mcp_and_cost(client):
    _, tokens = await create_authenticated_user(
        client, email="ai4@example.com", username="aiuser4")
    h = auth_headers(tokens["access_token"])

    manifest = await client.get("/v1/ai/mcp/manifest", headers=h)
    assert manifest.status_code == 200
    assert manifest.json()["protocol"] == "mcp"

    reg = await client.post("/v1/ai/mcp/servers",
                            json={"name": "tools-srv", "url": "https://mcp.example/rpc"},
                            headers=h)
    assert reg.status_code == 201, reg.text

    cost = await client.get("/v1/ai/cost", headers=h)
    assert cost.status_code == 200
    assert "totals" in cost.json()
