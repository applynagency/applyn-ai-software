"""Dispatcher coverage: failure paths, success paths, and custom agent dispatch."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.config import settings
from app.core.exceptions import AgentError
from app.database.session import AsyncSessionLocal
from app.repositories.user import UserRepository
from app.tests.conftest import (
    patch_approval_workflow_agent,
    patch_backend_architect_agent,
    patch_backend_v1_agent,
    patch_backend_v3_agent,
    patch_business_analyst_agent,
    patch_product_owner_agent,
    setup_product_execution_context,
)
from app.workflows.dispatcher import IMPLEMENTED_INTERNAL_AGENTS, AgentDispatcher

AGENT_PATCHES = {
    "product_owner": patch_product_owner_agent,
    "business_analyst": patch_business_analyst_agent,
}


async def _dispatcher_user(client, tokens: dict) -> tuple:
    me = await client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    async with AsyncSessionLocal() as session:
        user = await UserRepository(session).get_by_id(me.json()["id"])
        assert user is not None
        return session, user


@pytest.mark.parametrize(
    "internal_agent",
    [a for a in IMPLEMENTED_INTERNAL_AGENTS if a != "product_owner"],
)
async def test_dispatch_internal_missing_requirement(client, internal_agent):
    _, tokens = await __import__(
        "app.tests.conftest", fromlist=["create_authenticated_user"]
    ).create_authenticated_user(
        client,
        email=f"disp-miss-{internal_agent}@example.com",
        username=f"disp{internal_agent[:8]}",
    )
    session, user = await _dispatcher_user(client, tokens)
    dispatcher = AgentDispatcher()
    result = await dispatcher.dispatch_internal(
        internal_agent=internal_agent,
        requirement_content="content",
        session=session,
        requirement_id=str(uuid.uuid4()),
        user=user,
    )
    assert result.status == "failed"
    assert result.error_message
    assert "not found" in result.error_message.lower()


@pytest.mark.asyncio
async def test_dispatch_internal_unimplemented_agent():
    dispatcher = AgentDispatcher()
    result = await dispatcher.dispatch_internal(
        internal_agent="legacy_agent",
        requirement_content="x",
        session=AsyncMock(),
        requirement_id=str(uuid.uuid4()),
        user=AsyncMock(id=str(uuid.uuid4())),
    )
    assert result.status == "skipped"


@pytest.mark.asyncio
async def test_dispatch_product_owner_success(client):
    from app.tests.conftest import create_authenticated_user

    _, tokens = await create_authenticated_user(
        client, email="disp-po-ok@example.com", username="disppook"
    )
    ctx = await setup_product_execution_context(client, tokens["access_token"])
    session, user = await _dispatcher_user(client, tokens)
    dispatcher = AgentDispatcher()
    with patch_product_owner_agent():
        result = await dispatcher.dispatch_internal(
            internal_agent="product_owner",
            requirement_content=ctx["requirement"]["content"],
            session=session,
            requirement_id=ctx["requirement"]["id"],
            user=user,
        )
    assert result.status == "completed"
    assert result.agent_run_id
    assert result.output


@pytest.mark.asyncio
async def test_dispatch_business_analyst_success(client):
    from app.tests.conftest import create_authenticated_user, create_product_owner_run

    _, tokens = await create_authenticated_user(
        client, email="disp-ba-ok@example.com", username="dispbaok"
    )
    ctx = await setup_product_execution_context(client, tokens["access_token"])
    await create_product_owner_run(client, tokens["access_token"], ctx["requirement"]["id"])
    session, user = await _dispatcher_user(client, tokens)
    dispatcher = AgentDispatcher()
    with patch_business_analyst_agent():
        result = await dispatcher.dispatch_internal(
            internal_agent="business_analyst",
            requirement_content=ctx["requirement"]["content"],
            session=session,
            requirement_id=ctx["requirement"]["id"],
            user=user,
        )
    assert result.status == "completed"
    assert result.agent_run_id


DISPATCH_SUCCESS_CASES = [
    (
        "backend_architect",
        "app.tests.conftest.setup_backend_architect_pipeline",
        patch_backend_architect_agent,
    ),
    (
        "backend_v1",
        "app.tests.conftest.setup_backend_v1_pipeline",
        patch_backend_v1_agent,
    ),
    (
        "backend_v3",
        "app.tests.conftest.setup_backend_v3_pipeline",
        patch_backend_v3_agent,
    ),
    (
        "approval",
        "app.tests.conftest.setup_approval_pipeline",
        patch_approval_workflow_agent,
    ),
]


@pytest.mark.parametrize(
    "internal_agent,setup_path,patch_fn",
    DISPATCH_SUCCESS_CASES,
    ids=[c[0] for c in DISPATCH_SUCCESS_CASES],
)
async def test_dispatch_internal_agent_success(client, internal_agent, setup_path, patch_fn):
    import importlib

    from app.tests.conftest import (
        create_authenticated_user,
        create_project,
        create_requirement,
        create_workspace,
    )

    setup_mod, setup_name = setup_path.rsplit(".", 1)
    setup_fn = getattr(importlib.import_module(setup_mod), setup_name)

    _, tokens = await create_authenticated_user(
        client,
        email=f"disp-ok-{internal_agent}@example.com",
        username=f"dispok{internal_agent[:6]}",
    )
    if setup_name == "setup_backend_architect_pipeline":
        ctx = await setup_fn(client, tokens["access_token"])
        requirement_id = ctx["requirement"]["id"]
        requirement_content = ctx["requirement"]["content"]
    else:
        workspace = await create_workspace(
            client, tokens["access_token"], slug=f"disp-{internal_agent}-ws"
        )
        project = await create_project(
            client, tokens["access_token"], workspace_id=workspace["id"], slug=f"disp-{internal_agent}-p"
        )
        requirement = await create_requirement(
            client, tokens["access_token"], project_id=project["id"]
        )
        await setup_fn(client, tokens["access_token"], requirement["id"])
        requirement_id = requirement["id"]
        requirement_content = requirement["content"]

    session, user = await _dispatcher_user(client, tokens)
    dispatcher = AgentDispatcher()
    with patch_fn():
        result = await dispatcher.dispatch_internal(
            internal_agent=internal_agent,
            requirement_content=requirement_content,
            session=session,
            requirement_id=requirement_id,
            user=user,
        )
    assert result.status == "completed"
    assert result.agent_run_id


@pytest.mark.asyncio
async def test_dispatch_product_owner_agent_error(client):
    from app.tests.conftest import create_authenticated_user

    _, tokens = await create_authenticated_user(
        client, email="disp-po-fail@example.com", username="disppofail"
    )
    ctx = await setup_product_execution_context(client, tokens["access_token"])
    session, user = await _dispatcher_user(client, tokens)
    dispatcher = AgentDispatcher()
    with patch("app.workflows.dispatcher.ProductOwnerAgent.__init__", lambda self: None):
        with patch(
            "app.workflows.dispatcher.ProductOwnerAgent.run",
            new=AsyncMock(side_effect=AgentError("LLM failed")),
        ):
            result = await dispatcher.dispatch_internal(
                internal_agent="product_owner",
                requirement_content=ctx["requirement"]["content"],
                session=session,
                requirement_id=ctx["requirement"]["id"],
                user=user,
            )
    assert result.status == "failed"
    assert "LLM failed" in (result.error_message or "")


@pytest.mark.asyncio
async def test_dispatch_custom_agent_not_found():
    dispatcher = AgentDispatcher()
    session = AsyncMock()
    with patch("app.workflows.dispatcher.AIAgentRepository") as repo_cls:
        repo_cls.return_value.get_with_details = AsyncMock(return_value=None)
        result = await dispatcher.dispatch_custom(
            custom_agent_id=str(uuid.uuid4()),
            prompt_template=None,
            requirement_content="req",
            session=session,
        )
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_dispatch_custom_stub_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    dispatcher = AgentDispatcher()
    fake_agent = type(
        "Agent",
        (),
        {"id": "a1", "name": "Analyzer", "goal": "Analyze", "prompt_template": None},
    )()
    with patch("app.workflows.dispatcher.AIAgentRepository") as repo_cls:
        repo_cls.return_value.get_with_details = AsyncMock(return_value=fake_agent)
        result = await dispatcher.dispatch_custom(
            custom_agent_id="a1",
            prompt_template="Review",
            requirement_content="Build CRM",
            session=AsyncMock(),
        )
    assert result.status == "completed"
    assert result.output["mode"] == "stub"


@pytest.mark.asyncio
async def test_dispatch_custom_llm_success(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    dispatcher = AgentDispatcher()
    fake_agent = type(
        "Agent",
        (),
        {"id": "a1", "name": "Analyzer", "goal": "Analyze", "prompt_template": None},
    )()
    message = type(
        "Msg",
        (),
        {
            "content": [type("Block", (), {"text": '{"summary":"ok"}'})()],
            "usage": type("Usage", (), {"input_tokens": 1, "output_tokens": 2})(),
        },
    )()
    client = AsyncMock()
    client.messages.create = AsyncMock(return_value=message)
    with patch("app.workflows.dispatcher.AIAgentRepository") as repo_cls:
        repo_cls.return_value.get_with_details = AsyncMock(return_value=fake_agent)
        with patch("anthropic.AsyncAnthropic", return_value=client):
            result = await dispatcher.dispatch_custom(
                custom_agent_id="a1",
                prompt_template=None,
                requirement_content="Build CRM",
                session=AsyncMock(),
            )
    assert result.status == "completed"
    assert result.output["mode"] == "llm"


@pytest.mark.asyncio
async def test_dispatch_custom_llm_failure(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    dispatcher = AgentDispatcher()
    fake_agent = type(
        "Agent",
        (),
        {"id": "a1", "name": "Analyzer", "goal": "Analyze", "prompt_template": "P"},
    )()
    client = AsyncMock()
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(500, request=request)
    client.messages.create = AsyncMock(
        side_effect=__import__("anthropic").APIStatusError("boom", response=response, body=None)
    )
    with patch("app.workflows.dispatcher.AIAgentRepository") as repo_cls:
        repo_cls.return_value.get_with_details = AsyncMock(return_value=fake_agent)
        with patch("anthropic.AsyncAnthropic", return_value=client):
            result = await dispatcher.dispatch_custom(
                custom_agent_id="a1",
                prompt_template=None,
                requirement_content="req",
                session=AsyncMock(),
            )
    assert result.status == "failed"
