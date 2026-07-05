import pytest

from app.agents.deployment import DeploymentAgent
from app.core.exceptions import AgentError
from app.schemas.deployment import DeploymentOutput
from app.tests.conftest import mock_approval_workflow_output, mock_fullstack_assembly_output


def _sample_fsa_output() -> dict:
    return mock_fullstack_assembly_output().model_dump()


def _sample_approval_output() -> dict:
    return mock_approval_workflow_output().model_dump()


async def test_agent_run_returns_deployment_output():
    agent = DeploymentAgent()
    output = await agent.run(
        fullstack_assembly_output=_sample_fsa_output(),
        approval_output=_sample_approval_output(),
        app_name="generated-app",
        environment="production",
        deployment_provider="AZURE",
    )
    assert isinstance(output, DeploymentOutput)
    assert output.deployment_status == "DEPLOYED"
    assert output.live_url.endswith(".applyn.app")


async def test_agent_run_raises_on_empty_fullstack_assembly():
    agent = DeploymentAgent()
    with pytest.raises(AgentError, match="Full Stack Assembly output is required"):
        await agent.run(
            fullstack_assembly_output={},
            approval_output=_sample_approval_output(),
            app_name="generated-app",
            environment="production",
        )


async def test_agent_run_raises_on_empty_approval():
    agent = DeploymentAgent()
    with pytest.raises(AgentError, match="Approval output is required"):
        await agent.run(
            fullstack_assembly_output=_sample_fsa_output(),
            approval_output={},
            app_name="generated-app",
            environment="production",
        )


async def test_agent_initializes_deployer():
    agent = DeploymentAgent()
    assert agent.deployer is not None


async def test_agent_run_includes_deployment_logs():
    agent = DeploymentAgent()
    output = await agent.run(
        fullstack_assembly_output=_sample_fsa_output(),
        approval_output=_sample_approval_output(),
        app_name="generated-app",
        environment="staging",
        deployment_provider="AZURE",
    )
    assert len(output.deployment_logs) >= 1


async def test_agent_run_sets_rollback_available():
    agent = DeploymentAgent()
    output = await agent.run(
        fullstack_assembly_output=_sample_fsa_output(),
        approval_output=_sample_approval_output(),
        app_name="generated-app",
        environment="production",
    )
    assert output.rollback_available is True
