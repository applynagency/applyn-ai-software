"""Dispatcher coverage for critical execution paths."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher


@pytest.mark.asyncio
async def test_dispatch_internal_unimplemented_agent():
    dispatcher = AgentDispatcher()
    result = await dispatcher.dispatch_internal(
        internal_agent="not_real_agent",
        requirement_content="req",
        session=AsyncMock(),
        requirement_id=str(uuid.uuid4()),
        user=AsyncMock(id=str(uuid.uuid4())),
    )
    assert result.status == "skipped"


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_name", list(IMPLEMENTED_INTERNAL_AGENTS))
async def test_is_implemented_agents(agent_name):
    dispatcher = AgentDispatcher()
    assert dispatcher.is_implemented(agent_name)


@pytest.mark.asyncio
async def test_dispatch_custom_agent_not_found():
    dispatcher = AgentDispatcher()
    session = AsyncMock()
    session.execute = AsyncMock()
    with patch("app.workflows.dispatcher.AIAgentRepository") as repo_cls:
        repo = repo_cls.return_value
        repo.get_with_details = AsyncMock(return_value=None)
        result = await dispatcher.dispatch_custom(
            custom_agent_id=str(uuid.uuid4()),
            prompt_template=None,
            requirement_content="req",
            session=session,
        )
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_dispatch_custom_stub_without_api_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    dispatcher = AgentDispatcher()
    fake_agent = type("A", (), {"id": "a1", "name": "Custom", "goal": "g", "prompt_template": None})()
    with patch("app.workflows.dispatcher.AIAgentRepository") as repo_cls:
        repo = repo_cls.return_value
        repo.get_with_details = AsyncMock(return_value=fake_agent)
        result = await dispatcher.dispatch_custom(
            custom_agent_id="a1",
            prompt_template="Analyze",
            requirement_content="req",
            session=AsyncMock(),
        )
    assert result.status == "completed"
    assert result.output["mode"] == "stub"
