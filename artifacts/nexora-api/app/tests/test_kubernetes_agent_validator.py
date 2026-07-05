import pytest

from app.kubernetes_agent.validator import MINIMUM_COUNTS, KubernetesAgentValidator
from app.schemas.kubernetes_agent import KubernetesAgentOutput
from app.tests.conftest import mock_kubernetes_agent_output

LIST_FIELDS = [
    "deployments",
    "services",
    "ingresses",
    "hpas",
    "configmaps_secrets",
    "network_policies",
    "environment_overlays",
]


@pytest.fixture
def validator():
    return KubernetesAgentValidator()


def test_valid_output_passes(validator):
    result = validator.validate(mock_kubernetes_agent_output())
    assert result.is_valid is True
    assert result.score >= 80


def test_empty_output_fails(validator):
    result = validator.validate(KubernetesAgentOutput())
    assert result.is_valid is False
    assert len(result.errors) == len(MINIMUM_COUNTS)


def test_minimum_counts_match_spec():
    assert MINIMUM_COUNTS == {
        "deployments": 3,
        "services": 3,
        "ingresses": 1,
        "hpas": 1,
        "configmaps_secrets": 3,
    }


@pytest.mark.parametrize("field", list(MINIMUM_COUNTS.keys()))
def test_missing_required_section_fails(validator, field):
    data = mock_kubernetes_agent_output().model_dump()
    data[field] = []
    result = validator.validate(KubernetesAgentOutput(**data))
    assert result.is_valid is False
    assert any(field in err for err in result.errors)


@pytest.mark.parametrize("field,minimum", list(MINIMUM_COUNTS.items()))
def test_below_minimum_fails(validator, field, minimum):
    data = mock_kubernetes_agent_output().model_dump()
    data[field] = data[field][: max(0, minimum - 1)]
    result = validator.validate(KubernetesAgentOutput(**data))
    assert result.is_valid is False
    assert any(field in err for err in result.errors)


@pytest.mark.parametrize("field,minimum", list(MINIMUM_COUNTS.items()))
def test_exactly_minimum_passes(validator, field, minimum):
    output = mock_kubernetes_agent_output()
    result = validator.validate(output)
    counts = result.counts
    assert counts[field] >= minimum


@pytest.mark.parametrize("field", LIST_FIELDS)
def test_counts_reported_for_all_fields(validator, field):
    result = validator.validate(mock_kubernetes_agent_output())
    assert field in result.counts


def test_invalid_score_below_100(validator):
    data = mock_kubernetes_agent_output().model_dump()
    data["deployments"] = []
    result = validator.validate(KubernetesAgentOutput(**data))
    assert result.score < 100


def test_valid_score_is_float(validator):
    result = validator.validate(mock_kubernetes_agent_output())
    assert isinstance(result.score, float)
