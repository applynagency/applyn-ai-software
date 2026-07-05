import pytest

from app.agents.fullstack_assembly import FullStackAssemblyAgent
from app.core.exceptions import AgentError
from app.schemas.fullstack_assembly import FullstackAssemblyOutput
from app.tests.conftest import (
    mock_backend_execution_output,
    mock_backend_v3_output,
    mock_frontend_execution_output,
    mock_frontend_v3_output,
)


def _sample_fe_output() -> dict:
    return mock_frontend_execution_output().model_dump()


def _sample_fe_v3_output() -> dict:
    return mock_frontend_v3_output().model_dump()


def _sample_be_output() -> dict:
    return mock_backend_execution_output().model_dump()


def _sample_be_v3_output() -> dict:
    return mock_backend_v3_output().model_dump()


async def test_agent_run_returns_assembly_output():
    agent = FullStackAssemblyAgent()
    output = await agent.run(
        requirement_text="Deploy onboarding flow",
        frontend_execution_output=_sample_fe_output(),
        frontend_v3_output=_sample_fe_v3_output(),
        backend_execution_output=_sample_be_output(),
        backend_v3_output=_sample_be_v3_output(),
    )
    assert isinstance(output, FullstackAssemblyOutput)
    assert output.assembly_status == "ASSEMBLY_APPROVED"


async def test_agent_run_raises_on_empty_frontend_execution():
    agent = FullStackAssemblyAgent()
    with pytest.raises(AgentError, match="Frontend execution output is required"):
        await agent.run(
            requirement_text="Test",
            frontend_execution_output={},
            frontend_v3_output=_sample_fe_v3_output(),
            backend_execution_output=_sample_be_output(),
            backend_v3_output=_sample_be_v3_output(),
        )


async def test_agent_run_raises_on_empty_backend_execution():
    agent = FullStackAssemblyAgent()
    with pytest.raises(AgentError, match="Backend execution output is required"):
        await agent.run(
            requirement_text="Test",
            frontend_execution_output=_sample_fe_output(),
            frontend_v3_output=_sample_fe_v3_output(),
            backend_execution_output={},
            backend_v3_output=_sample_be_v3_output(),
        )


async def test_agent_run_raises_on_missing_frontend_generated_files():
    agent = FullStackAssemblyAgent()
    with pytest.raises(AgentError, match="generated files"):
        await agent.run(
            requirement_text="Test",
            frontend_execution_output=_sample_fe_output(),
            frontend_v3_output={"generated_files": []},
            backend_execution_output=_sample_be_output(),
            backend_v3_output=_sample_be_v3_output(),
        )


async def test_agent_run_raises_on_missing_backend_generated_files():
    agent = FullStackAssemblyAgent()
    with pytest.raises(AgentError, match="generated files"):
        await agent.run(
            requirement_text="Test",
            frontend_execution_output=_sample_fe_output(),
            frontend_v3_output=_sample_fe_v3_output(),
            backend_execution_output=_sample_be_output(),
            backend_v3_output={"generated_files": []},
        )


async def test_agent_run_includes_backend_package():
    agent = FullStackAssemblyAgent()
    output = await agent.run(
        requirement_text="Full stack app",
        frontend_execution_output=_sample_fe_output(),
        frontend_v3_output=_sample_fe_v3_output(),
        backend_execution_output=_sample_be_output(),
        backend_v3_output=_sample_be_v3_output(),
    )
    assert output.backend_package["included"] is True
    assert output.health_checks
    assert output.release_metadata


async def test_agent_initializes_assembler():
    agent = FullStackAssemblyAgent()
    assert agent.assembler is not None
