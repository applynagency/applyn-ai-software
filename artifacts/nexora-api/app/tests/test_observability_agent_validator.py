import pytest

from app.observability_agent.validator import (
    MINIMUM_COUNTS,
    REQUIRED_TEXT_FIELDS,
    ObservabilityAgentValidator,
)
from app.schemas.observability_agent import ObservabilityAgentOutput
from app.tests.conftest import mock_observability_agent_output


@pytest.fixture
def validator():
    return ObservabilityAgentValidator()


def test_valid_output_passes(validator):
    result = validator.validate(mock_observability_agent_output())
    assert result.is_valid is True
    assert result.score >= 80


def test_empty_output_fails(validator):
    result = validator.validate(ObservabilityAgentOutput())
    assert result.is_valid is False
    assert len(result.errors) == len(MINIMUM_COUNTS) + len(REQUIRED_TEXT_FIELDS)


def test_minimum_counts_match_spec():
    assert MINIMUM_COUNTS == {
        "alert_rules": 5,
        "grafana_dashboards": 3,
        "slo_definitions": 3,
        "logging_flows": 3,
    }


@pytest.mark.parametrize("field", list(MINIMUM_COUNTS.keys()))
def test_missing_required_list_fails(validator, field):
    data = mock_observability_agent_output().model_dump()
    data[field] = []
    result = validator.validate(ObservabilityAgentOutput(**data))
    assert result.is_valid is False
    assert any(field in err for err in result.errors)


@pytest.mark.parametrize("field,minimum", list(MINIMUM_COUNTS.items()))
def test_below_minimum_fails(validator, field, minimum):
    data = mock_observability_agent_output().model_dump()
    data[field] = data[field][: max(0, minimum - 1)]
    result = validator.validate(ObservabilityAgentOutput(**data))
    assert result.is_valid is False
    assert any(field in err for err in result.errors)


@pytest.mark.parametrize("field", REQUIRED_TEXT_FIELDS)
def test_missing_text_field_fails(validator, field):
    data = mock_observability_agent_output().model_dump()
    data[field] = ""
    result = validator.validate(ObservabilityAgentOutput(**data))
    assert result.is_valid is False
    assert any(field in err for err in result.errors)


@pytest.mark.parametrize("field", REQUIRED_TEXT_FIELDS)
def test_whitespace_text_field_fails(validator, field):
    data = mock_observability_agent_output().model_dump()
    data[field] = "   "
    result = validator.validate(ObservabilityAgentOutput(**data))
    assert result.is_valid is False


@pytest.mark.parametrize("field", list(MINIMUM_COUNTS.keys()))
def test_counts_reported(validator, field):
    result = validator.validate(mock_observability_agent_output())
    assert field in result.counts


def test_valid_score_is_float(validator):
    result = validator.validate(mock_observability_agent_output())
    assert isinstance(result.score, float)
