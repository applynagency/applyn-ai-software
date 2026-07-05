import pytest

from app.integration_test.validator import MINIMUM_COUNTS, IntegrationTestValidator
from app.schemas.integration_test import IntegrationTestItem, IntegrationTestOutput
from app.tests.conftest import mock_integration_test_output


@pytest.fixture
def validator():
    return IntegrationTestValidator()


def test_valid_output_passes(validator):
    result = validator.validate(mock_integration_test_output())
    assert result.is_valid is True
    assert result.score >= 80
    assert not result.errors


def test_validation_score_present(validator):
    result = validator.validate(mock_integration_test_output())
    assert 0 <= result.score <= 100


def test_validation_score_is_rounded(validator):
    result = validator.validate(mock_integration_test_output())
    assert result.score == round(result.score, 2)


def test_empty_output_fails(validator):
    result = validator.validate(IntegrationTestOutput())
    assert result.is_valid is False
    assert len(result.errors) >= len(MINIMUM_COUNTS)


def _build_items(field: str, count: int):
    return [
        IntegrationTestItem(
            id=f"{field}-{i:03d}",
            name=f"{field} item {i}",
            description=f"{field} desc {i}",
            expected_result="OK"
        )
        for i in range(1, count + 1)
    ]


@pytest.mark.parametrize(
    "field,minimum",
    list(MINIMUM_COUNTS.items()),
)
@pytest.mark.parametrize("delta", [1, 2, 3])
def test_each_required_section_fails_below_minimum(validator, field, minimum, delta):
    output = mock_integration_test_output()
    setattr(output, field, _build_items(field, max(minimum - delta, 0)))
    result = validator.validate(output)
    assert result.is_valid is False
    assert any(field in err for err in result.errors)


@pytest.mark.parametrize(
    "field,minimum",
    list(MINIMUM_COUNTS.items()),
)
@pytest.mark.parametrize("padding", [0, 1, 3])
def test_each_required_section_passes_at_or_above_minimum(validator, field, minimum, padding):
    output = mock_integration_test_output()
    setattr(output, field, _build_items(field, minimum + padding))
    result = validator.validate(output)
    assert not any(field in err for err in result.errors)


@pytest.mark.parametrize(
    "field,minimum",
    list(MINIMUM_COUNTS.items()),
)
def test_counts_report_actual_values(validator, field, minimum):
    output = mock_integration_test_output()
    setattr(output, field, _build_items(field, minimum + 2))
    result = validator.validate(output)
    assert result.counts[field] == minimum + 2


@pytest.mark.parametrize("field", list(MINIMUM_COUNTS.keys()))
def test_error_message_contains_field_name(validator, field):
    output = mock_integration_test_output()
    setattr(output, field, [])
    result = validator.validate(output)
    assert any(field in err for err in result.errors)


@pytest.mark.parametrize("field", list(MINIMUM_COUNTS.keys()))
def test_score_decreases_when_single_field_empty(validator, field):
    output = mock_integration_test_output()
    setattr(output, field, [])
    result = validator.validate(output)
    assert result.score < 100


@pytest.mark.parametrize("extra", [0, 1, 5, 10])
def test_extra_items_do_not_break_validation(validator, extra):
    output = mock_integration_test_output()
    for field, minimum in MINIMUM_COUNTS.items():
        setattr(output, field, _build_items(field, minimum + extra))
    result = validator.validate(output)
    assert result.is_valid is True


@pytest.mark.parametrize("coverage", [{}, None])
def test_coverage_object_requirement(validator, coverage):
    output = mock_integration_test_output()
    if coverage is None:
        output = IntegrationTestOutput(**(mock_integration_test_output().model_dump() | {"integration_coverage": {}}))
    else:
        output.integration_coverage = coverage
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("integration_coverage" in err for err in result.errors)
