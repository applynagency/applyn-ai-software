"""Direct unit tests for internal agent implementations (mocked LLM)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.config import settings
from app.core.exceptions import AgentError
from app.tests.conftest import (
    mock_approval_workflow_output,
    mock_backend_architect_output,
    mock_backend_code_review_output,
    mock_backend_v1_output,
    mock_backend_v2_output,
    mock_backend_v3_output,
    mock_business_analyst_output,
    mock_frontend_architect_output,
    mock_frontend_code_review_output,
    mock_frontend_execution_output,
    mock_frontend_v1_output,
    mock_frontend_v2_output,
    mock_frontend_v3_output,
    mock_fullstack_assembly_output,
    mock_product_owner_output,
    mock_uiux_designer_output,
)


def _anthropic_message(payload: dict, *, tokens: int = 100) -> SimpleNamespace:
    block = SimpleNamespace(type="text", text=json.dumps(payload))
    usage = SimpleNamespace(input_tokens=tokens // 2, output_tokens=tokens // 2)
    return SimpleNamespace(content=[block], usage=usage)


def _patch_anthropic_client(payload: dict):
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_anthropic_message(payload))
    return patch("anthropic.AsyncAnthropic", return_value=client)


@pytest.fixture(autouse=True)
def configured_anthropic_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")


@pytest.mark.asyncio
async def test_product_owner_agent_run_success():
    from app.agents.product_owner import ProductOwnerAgent

    payload = mock_product_owner_output().model_dump()
    with _patch_anthropic_client(payload):
        agent = ProductOwnerAgent()
        output, tokens = await agent.run("Build onboarding")
    assert output.total_story_points == payload["total_story_points"]
    assert tokens == 100


@pytest.mark.asyncio
async def test_product_owner_agent_auth_error():
    from app.agents.product_owner import ProductOwnerAgent

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(401, request=request)
    client = MagicMock()
    client.messages.create = AsyncMock(
        side_effect=__import__("anthropic").AuthenticationError(
            "bad key", response=response, body=None
        )
    )
    with patch("anthropic.AsyncAnthropic", return_value=client):
        agent = ProductOwnerAgent()
        with pytest.raises(AgentError, match="ANTHROPIC_API_KEY"):
            await agent.run("req")


@pytest.mark.asyncio
async def test_product_owner_agent_empty_response():
    from app.agents.product_owner import ProductOwnerAgent

    message = SimpleNamespace(content=[], usage=SimpleNamespace(input_tokens=1, output_tokens=0))
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=message)
    with patch("anthropic.AsyncAnthropic", return_value=client):
        agent = ProductOwnerAgent()
        with pytest.raises(AgentError, match="Empty response"):
            await agent.run("req")


@pytest.mark.asyncio
async def test_business_analyst_agent_run_success():
    from app.agents.business_analyst import BusinessAnalystAgent

    payload = mock_business_analyst_output().model_dump(mode="json")
    with _patch_anthropic_client(payload):
        agent = BusinessAnalystAgent()
        output, tokens = await agent.run(
            requirement_text="Analyze",
            product_owner_output=mock_product_owner_output().model_dump(),
        )
    assert output.functional_requirements
    assert tokens == 100


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "agent_import,agent_class,run_kwargs,payload_factory",
    [
        (
            "app.agents.backend_architect",
            "BackendArchitectAgent",
            {"requirement_text": "x", "business_analyst_output": {}},
            mock_backend_architect_output,
        ),
        (
            "app.agents.backend_v1",
            "BackendDeveloperV1Agent",
            {"requirement_text": "x", "backend_architect_output": {}},
            mock_backend_v1_output,
        ),
        (
            "app.agents.backend_v2",
            "BackendDeveloperV2Agent",
            {"requirement_text": "x", "backend_v1_output": {}},
            mock_backend_v2_output,
        ),
        (
            "app.agents.backend_v3",
            "BackendDeveloperV3Agent",
            {"requirement_text": "x", "backend_v2_output": {}},
            mock_backend_v3_output,
        ),
        (
            "app.agents.backend_code_review",
            "BackendCodeReviewAgent",
            {"requirement_text": "x", "backend_v3_output": {}},
            mock_backend_code_review_output,
        ),
        (
            "app.agents.uiux_designer",
            "UIUXDesignerAgent",
            {"requirement_text": "x", "business_analyst_output": {}},
            mock_uiux_designer_output,
        ),
        (
            "app.agents.frontend_architect",
            "FrontendArchitectAgent",
            {"requirement_text": "x", "uiux_output": {}},
            mock_frontend_architect_output,
        ),
        (
            "app.agents.frontend_v1",
            "FrontendDeveloperV1Agent",
            {"requirement_text": "x", "frontend_architect_output": {}},
            mock_frontend_v1_output,
        ),
        (
            "app.agents.frontend_v2",
            "FrontendDeveloperV2Agent",
            {"requirement_text": "x", "frontend_v1_output": {}},
            mock_frontend_v2_output,
        ),
        (
            "app.agents.frontend_v3",
            "FrontendDeveloperV3Agent",
            {"requirement_text": "x", "frontend_v2_output": {}},
            mock_frontend_v3_output,
        ),
        (
            "app.agents.frontend_code_review",
            "FrontendCodeReviewAgent",
            {"requirement_text": "x", "frontend_v3_output": {}},
            mock_frontend_code_review_output,
        ),
    ],
)
async def test_llm_agents_run_success(agent_import, agent_class, run_kwargs, payload_factory):
    import importlib

    module = importlib.import_module(agent_import)
    agent_cls = getattr(module, agent_class)
    payload = payload_factory().model_dump(mode="json")
    for key in run_kwargs:
        if key.endswith("_output") and not run_kwargs[key]:
            run_kwargs[key] = payload
    with _patch_anthropic_client(payload):
        agent = agent_cls()
        output, tokens = await agent.run(**run_kwargs)
    assert output is not None
    assert tokens == 100


@pytest.mark.asyncio
async def test_frontend_execution_agent_run():
    from app.agents.frontend_execution import FrontendExecutionAgent

    agent = FrontendExecutionAgent()
    output = await agent.run(
        frontend_code_review_output=mock_frontend_code_review_output().model_dump(mode="json"),
        frontend_v3_output=mock_frontend_v3_output().model_dump(mode="json"),
    )
    assert output.build_status in {"success", "failed"}


@pytest.mark.asyncio
async def test_fullstack_assembly_agent_run():
    from app.agents.fullstack_assembly import FullStackAssemblyAgent
    from app.tests.conftest import mock_backend_execution_output, mock_backend_v3_output

    agent = FullStackAssemblyAgent()
    output = await agent.run(
        requirement_text="Ship onboarding",
        frontend_execution_output=mock_frontend_execution_output().model_dump(mode="json"),
        frontend_v3_output=mock_frontend_v3_output().model_dump(mode="json"),
        backend_execution_output=mock_backend_execution_output().model_dump(mode="json"),
        backend_v3_output=mock_backend_v3_output().model_dump(mode="json"),
    )
    assert output.assembly_status


@pytest.mark.asyncio
async def test_approval_agent_run():
    from app.agents.approval import ApprovalWorkflowAgent

    agent = ApprovalWorkflowAgent()
    output = await agent.run(
        requirement_text="Ship onboarding",
        frontend_execution_output=mock_frontend_execution_output().model_dump(mode="json"),
        frontend_code_review_output=mock_frontend_code_review_output().model_dump(mode="json"),
        fullstack_assembly_output=mock_fullstack_assembly_output().model_dump(mode="json"),
    )
    assert output.approval_status


@pytest.mark.asyncio
async def test_deployment_agent_run():
    from app.agents.deployment import DeploymentAgent

    agent = DeploymentAgent()
    output = await agent.run(
        fullstack_assembly_output=mock_fullstack_assembly_output().model_dump(mode="json"),
        approval_output=mock_approval_workflow_output().model_dump(mode="json"),
        app_name="demo",
        environment="staging",
    )
    assert output.deployment_status


@pytest.mark.asyncio
async def test_deployment_agent_requires_inputs():
    from app.agents.deployment import DeploymentAgent

    agent = DeploymentAgent()
    with pytest.raises(AgentError, match="Full Stack Assembly"):
        await agent.run(
            fullstack_assembly_output={},
            approval_output=mock_approval_workflow_output().model_dump(mode="json"),
            app_name="demo",
            environment="staging",
        )
