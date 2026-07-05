import pytest

from app.infrastructure_architect.validator import (
    MINIMUM_COUNTS,
    REQUIRED_TEXT_FIELDS,
    InfrastructureArchitectValidator,
)
from app.schemas.infrastructure_architect import (
    BackupRecoveryPlan,
    Environment,
    InfrastructureArchitectOutput,
    ScalingRule,
    SecurityControl,
)
from app.tests.conftest import mock_infrastructure_architect_output

ITEM_BUILDERS = {
    "environments": lambda i: Environment(id=f"ENV-{i:03d}", name=f"env-{i}", description="d"),
    "scaling_rules": lambda i: ScalingRule(id=f"SCALE-{i:03d}", name=f"rule-{i}", description="d"),
    "security_controls": lambda i: SecurityControl(id=f"SEC-{i:03d}", name=f"sec-{i}", description="d"),
    "backup_recovery_plans": lambda i: BackupRecoveryPlan(id=f"BR-{i:03d}", name=f"br-{i}", description="d"),
}


@pytest.fixture
def validator():
    return InfrastructureArchitectValidator()


def test_valid_output_passes(validator):
    result = validator.validate(mock_infrastructure_architect_output())
    assert result.is_valid is True
    assert result.score >= 80


def test_empty_output_fails(validator):
    result = validator.validate(InfrastructureArchitectOutput())
    assert result.is_valid is False


def _build_items(field: str, count: int):
    builder = ITEM_BUILDERS[field]
    return [builder(i) for i in range(1, count + 1)]


@pytest.mark.parametrize("field,minimum", list(MINIMUM_COUNTS.items()))
@pytest.mark.parametrize("delta", [1, 2, 3])
def test_each_list_field_fails_below_minimum(validator, field, minimum, delta):
    output = mock_infrastructure_architect_output()
    setattr(output, field, _build_items(field, max(minimum - delta, 0)))
    result = validator.validate(output)
    assert result.is_valid is False
    assert any(field in err for err in result.errors)


@pytest.mark.parametrize("field,minimum", list(MINIMUM_COUNTS.items()))
@pytest.mark.parametrize("padding", [0, 1, 3])
def test_each_list_field_passes_at_minimum(validator, field, minimum, padding):
    output = mock_infrastructure_architect_output()
    setattr(output, field, _build_items(field, minimum + padding))
    result = validator.validate(output)
    assert not any(field in err for err in result.errors)


@pytest.mark.parametrize("field", REQUIRED_TEXT_FIELDS)
def test_required_text_field_empty_fails(validator, field):
    data = mock_infrastructure_architect_output().model_dump()
    data[field] = ""
    result = validator.validate(InfrastructureArchitectOutput(**data))
    assert result.is_valid is False
    assert any(field in err for err in result.errors)


@pytest.mark.parametrize("field", REQUIRED_TEXT_FIELDS)
def test_required_text_field_present_passes(validator, field):
    result = validator.validate(mock_infrastructure_architect_output())
    assert not any(field in err for err in result.errors)


@pytest.mark.parametrize("field", list(MINIMUM_COUNTS.keys()))
def test_counts_report_actual_values(validator, field):
    output = mock_infrastructure_architect_output()
    setattr(output, field, _build_items(field, MINIMUM_COUNTS[field] + 2))
    result = validator.validate(output)
    assert result.counts[field] == MINIMUM_COUNTS[field] + 2
