import pytest

from app.docker_agent.validator import REQUIRED_SECTIONS, DockerAgentValidator
from app.schemas.docker_agent import DockerAgentOutput
from app.tests.conftest import mock_docker_agent_output


@pytest.fixture
def validator():
    return DockerAgentValidator()


def test_valid_output_passes(validator):
    result = validator.validate(mock_docker_agent_output())
    assert result.is_valid is True
    assert result.score >= 80


def test_empty_output_fails(validator):
    result = validator.validate(DockerAgentOutput())
    assert result.is_valid is False
    assert len(result.errors) == len(REQUIRED_SECTIONS)


@pytest.mark.parametrize("field", REQUIRED_SECTIONS)
def test_missing_section_fails(validator, field):
    data = mock_docker_agent_output().model_dump()
    data[field] = ""
    result = validator.validate(DockerAgentOutput(**data))
    assert result.is_valid is False
    assert any(field in err for err in result.errors)


@pytest.mark.parametrize("field", REQUIRED_SECTIONS)
def test_section_present_passes(validator, field):
    result = validator.validate(mock_docker_agent_output())
    assert not any(field in err for err in result.errors)


@pytest.mark.parametrize("field", REQUIRED_SECTIONS)
@pytest.mark.parametrize("value", ["x", "section content", "detailed plan"])
def test_whitespace_only_fails(validator, field, value):
    data = mock_docker_agent_output().model_dump()
    data[field] = "   " if value == "x" else value
    if value == "x":
        result = validator.validate(DockerAgentOutput(**data))
        assert result.is_valid is False
