from unittest.mock import AsyncMock, patch

import pytest

from app.agents.frontend_execution import FrontendExecutionAgent
from app.core.exceptions import AgentError
from app.schemas.frontend_execution import FrontendExecutionOutput
from app.tests.conftest import mock_frontend_execution_output


def _sample_v3_output() -> dict:
    return {
        "generated_files": [
            {"path": "package.json", "content": "{}"},
        ]
    }


def _sample_review_output() -> dict:
    return {"approval_status": "APPROVED_WITH_WARNINGS"}


async def test_agent_run_returns_execution_output():
    agent = FrontendExecutionAgent()
    expected = mock_frontend_execution_output()

    with patch.object(agent.executor, "execute", new=AsyncMock(return_value=expected)):
        output = await agent.run(
            frontend_v3_output=_sample_v3_output(),
            frontend_code_review_output=_sample_review_output(),
        )

    assert isinstance(output, FrontendExecutionOutput)
    assert output.build_status == "success"


async def test_agent_run_raises_on_empty_generated_files():
    agent = FrontendExecutionAgent()

    with pytest.raises(AgentError, match="no generated files"):
        await agent.run(
            frontend_v3_output={"generated_files": []},
            frontend_code_review_output=_sample_review_output(),
        )


async def test_agent_run_propagates_executor_agent_error():
    agent = FrontendExecutionAgent()

    with patch.object(
        agent.executor,
        "execute",
        new=AsyncMock(side_effect=AgentError("build pipeline failed")),
    ):
        with pytest.raises(AgentError, match="build pipeline failed"):
            await agent.run(
                frontend_v3_output=_sample_v3_output(),
                frontend_code_review_output=_sample_review_output(),
            )


async def test_agent_run_wraps_unexpected_errors():
    agent = FrontendExecutionAgent()

    with patch.object(
        agent.executor,
        "execute",
        new=AsyncMock(side_effect=RuntimeError("unexpected")),
    ):
        with pytest.raises(AgentError, match="Frontend execution failed"):
            await agent.run(
                frontend_v3_output=_sample_v3_output(),
                frontend_code_review_output=_sample_review_output(),
            )


def test_agent_initializes_executor():
    agent = FrontendExecutionAgent()
    assert agent.executor is not None
