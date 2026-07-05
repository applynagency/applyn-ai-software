import pytest

from app.agents.approval import ApprovalWorkflowAgent
from app.core.exceptions import AgentError
from app.schemas.approval import ApprovalWorkflowOutput
from app.tests.conftest import (
    mock_frontend_code_review_output,
    mock_frontend_execution_output,
    mock_fullstack_assembly_output,
)


def _sample_fe_output() -> dict:
    return mock_frontend_execution_output().model_dump()


def _sample_fcr_output() -> dict:
    return mock_frontend_code_review_output().model_dump(mode="json")


def _sample_fsa_output() -> dict:
    return mock_fullstack_assembly_output().model_dump()


async def test_agent_run_returns_approval_output():
    agent = ApprovalWorkflowAgent()
    output = await agent.run(
        requirement_text="Deploy onboarding flow for approval",
        frontend_execution_output=_sample_fe_output(),
        frontend_code_review_output=_sample_fcr_output(),
        fullstack_assembly_output=_sample_fsa_output(),
    )
    assert isinstance(output, ApprovalWorkflowOutput)
    assert output.approval_status == "UNDER_REVIEW"
    assert output.recommendation in ("APPROVE", "REVIEW", "REJECT")


async def test_agent_run_raises_on_empty_frontend_execution():
    agent = ApprovalWorkflowAgent()
    with pytest.raises(AgentError, match="Frontend execution output is required"):
        await agent.run(
            requirement_text="Test",
            frontend_execution_output={},
            frontend_code_review_output=_sample_fcr_output(),
            fullstack_assembly_output=_sample_fsa_output(),
        )


async def test_agent_run_raises_on_empty_frontend_code_review():
    agent = ApprovalWorkflowAgent()
    with pytest.raises(AgentError, match="Frontend code review output is required"):
        await agent.run(
            requirement_text="Test",
            frontend_execution_output=_sample_fe_output(),
            frontend_code_review_output={},
            fullstack_assembly_output=_sample_fsa_output(),
        )


async def test_agent_run_raises_on_empty_fullstack_assembly():
    agent = ApprovalWorkflowAgent()
    with pytest.raises(AgentError, match="Full Stack Assembly output is required"):
        await agent.run(
            requirement_text="Test",
            frontend_execution_output=_sample_fe_output(),
            frontend_code_review_output=_sample_fcr_output(),
            fullstack_assembly_output={},
        )


async def test_agent_initializes_processor():
    agent = ApprovalWorkflowAgent()
    assert agent.processor is not None
