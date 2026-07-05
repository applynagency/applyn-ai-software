import pytest

from app.cicd_agent.validator import REQUIRED_SECTIONS, CicdAgentValidator
from app.schemas.cicd_agent import CicdAgentOutput
from app.tests.conftest import mock_cicd_agent_output


@pytest.fixture
def validator():
    return CicdAgentValidator()


def test_valid_output_passes(validator):
    result = validator.validate(mock_cicd_agent_output())
    assert result.is_valid is True
    assert result.score >= 80


def test_empty_output_fails(validator):
    result = validator.validate(CicdAgentOutput())
    assert result.is_valid is False
    assert len(result.errors) == len(REQUIRED_SECTIONS)


@pytest.mark.parametrize("field", REQUIRED_SECTIONS)
def test_missing_section_fails(validator, field):
    data = mock_cicd_agent_output().model_dump()
    data[field] = ""
    result = validator.validate(CicdAgentOutput(**data))
    assert result.is_valid is False
    assert any(field in err for err in result.errors)


@pytest.mark.parametrize("field", REQUIRED_SECTIONS)
def test_section_present_passes(validator, field):
    result = validator.validate(mock_cicd_agent_output())
    assert not any(field in err for err in result.errors)


@pytest.mark.parametrize("field", REQUIRED_SECTIONS)
def test_whitespace_section_fails(validator, field):
    data = mock_cicd_agent_output().model_dump()
    data[field] = "   "
    result = validator.validate(CicdAgentOutput(**data))
    assert result.is_valid is False
