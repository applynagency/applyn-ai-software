"""LLM agent edge cases: rate limits, malformed JSON, and generic API failures."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.config import settings
from app.core.exceptions import AgentError


@pytest.fixture(autouse=True)
def configured_anthropic_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")


def _client_with_side_effect(side_effect):
    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=side_effect)
    return patch("anthropic.AsyncAnthropic", return_value=client)

RUN_KWARGS = {
    "BusinessAnalystAgent": {"requirement_text": "x", "product_owner_output": {}},
    "BackendArchitectAgent": {"requirement_text": "x", "business_analyst_output": {}},
    "BackendDeveloperV1Agent": {"requirement_text": "x", "backend_architect_output": {}},
    "UIUXDesignerAgent": {"requirement_text": "x", "business_analyst_output": {}},
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "agent_import,agent_class",
    [
        ("app.agents.product_owner", "ProductOwnerAgent"),
        ("app.agents.business_analyst", "BusinessAnalystAgent"),
        ("app.agents.backend_architect", "BackendArchitectAgent"),
        ("app.agents.backend_v1", "BackendDeveloperV1Agent"),
        ("app.agents.uiux_designer", "UIUXDesignerAgent"),
    ],
)
async def test_llm_agents_rate_limit_error(agent_import, agent_class):
    import importlib

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(429, request=request)
    error = __import__("anthropic").RateLimitError("rate limited", response=response, body=None)
    with _client_with_side_effect(error):
        module = importlib.import_module(agent_import)
        agent_cls = getattr(module, agent_class)
        agent = agent_cls()
        with pytest.raises(AgentError, match="rate limit|LLM call failed"):
            if agent_class == "ProductOwnerAgent":
                await agent.run("requirement")
            else:
                await agent.run(**RUN_KWARGS[agent_class])


@pytest.mark.asyncio
async def test_product_owner_json_decode_error():
    from app.agents.product_owner import ProductOwnerAgent

    block = SimpleNamespace(type="text", text="not-json")
    message = SimpleNamespace(content=[block], usage=SimpleNamespace(input_tokens=1, output_tokens=1))
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=message)
    with patch("anthropic.AsyncAnthropic", return_value=client):
        agent = ProductOwnerAgent()
        with pytest.raises(AgentError, match="Failed to parse"):
            await agent.run("requirement")


@pytest.mark.asyncio
async def test_product_owner_strips_markdown_fences():
    from app.agents.product_owner import ProductOwnerAgent
    from app.tests.conftest import mock_product_owner_output

    payload = mock_product_owner_output().model_dump()
    wrapped = f"```json\n{json.dumps(payload)}\n```"
    block = SimpleNamespace(type="text", text=wrapped)
    message = SimpleNamespace(content=[block], usage=SimpleNamespace(input_tokens=10, output_tokens=90))
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=message)
    with patch("anthropic.AsyncAnthropic", return_value=client):
        agent = ProductOwnerAgent()
        output, tokens = await agent.run("requirement")
    assert output.total_story_points == payload["total_story_points"]
    assert tokens == 100


@pytest.mark.asyncio
async def test_product_owner_generic_api_error():
    from app.agents.product_owner import ProductOwnerAgent

    with _client_with_side_effect(RuntimeError("network down")):
        agent = ProductOwnerAgent()
        with pytest.raises(AgentError, match="LLM call failed"):
            await agent.run("requirement")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "agent_import,agent_class,run_kwargs",
    [
        (
            "app.agents.business_analyst",
            "BusinessAnalystAgent",
            {"requirement_text": "x", "product_owner_output": {}},
        ),
        (
            "app.agents.backend_architect",
            "BackendArchitectAgent",
            {"requirement_text": "x", "business_analyst_output": {}},
        ),
        (
            "app.agents.backend_v1",
            "BackendDeveloperV1Agent",
            {"requirement_text": "x", "backend_architect_output": {}},
        ),
    ],
)
async def test_llm_agents_json_decode_error(agent_import, agent_class, run_kwargs):
    import importlib

    module = importlib.import_module(agent_import)
    agent_cls = getattr(module, agent_class)
    block = SimpleNamespace(type="text", text="{bad json")
    message = SimpleNamespace(content=[block], usage=SimpleNamespace(input_tokens=1, output_tokens=1))
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=message)
    with patch("anthropic.AsyncAnthropic", return_value=client):
        agent = agent_cls()
        with pytest.raises(AgentError, match="Failed to parse|JSON"):
            await agent.run(**run_kwargs)


@pytest.mark.asyncio
async def test_product_owner_missing_api_key(monkeypatch):
    from app.agents.product_owner import ProductOwnerAgent

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    with pytest.raises(AgentError, match="ANTHROPIC_API_KEY"):
        ProductOwnerAgent()
