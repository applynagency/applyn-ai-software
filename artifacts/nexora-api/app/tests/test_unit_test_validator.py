import pytest

from app.schemas.unit_test import TestFixture, UnitTestGeneratorOutput, UnitTestSpecification
from app.tests.conftest import mock_unit_test_generator_output
from app.unit_test_generator.validator import MINIMUM_COUNTS, UnitTestGeneratorValidator


@pytest.fixture
def validator():
    return UnitTestGeneratorValidator()


def test_valid_output_passes(validator):
    result = validator.validate(mock_unit_test_generator_output())
    assert result.is_valid is True
    assert result.score >= 80
    assert not result.errors


def test_validation_counts_reported(validator):
    result = validator.validate(mock_unit_test_generator_output())
    assert result.counts["frontend_specs"] == 5
    assert result.counts["backend_specs"] == 5
    assert result.counts["test_fixtures"] == 3


def test_empty_output_fails(validator):
    result = validator.validate(UnitTestGeneratorOutput())
    assert result.is_valid is False
    assert len(result.errors) == len(MINIMUM_COUNTS) + 2


def test_score_is_rounded(validator):
    result = validator.validate(mock_unit_test_generator_output())
    assert result.score == round(result.score, 2)


@pytest.mark.parametrize("count", [0, 1, 2, 4])
def test_frontend_specs_boundary_fails_below_minimum(validator, count):
    output = mock_unit_test_generator_output()
    output.frontend_unit_test_specifications = [
        UnitTestSpecification(
            id=f"FE-UT-{i}",
            name=f"FE {i}",
            description=f"Frontend test {i}",
            target_module=f"module_{i}.tsx",
            test_type="unit",
            assertions=["assert 1"],
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("frontend_specs" in err for err in result.errors)


@pytest.mark.parametrize("count", [5, 6, 10])
def test_frontend_specs_boundary_passes_at_minimum(validator, count):
    output = mock_unit_test_generator_output()
    output.frontend_unit_test_specifications = [
        UnitTestSpecification(
            id=f"FE-UT-{i}",
            name=f"FE {i}",
            description=f"Frontend test {i}",
            target_module=f"module_{i}.tsx",
            test_type="unit",
            assertions=["assert 1"],
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert "frontend_specs" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 2, 4])
def test_backend_specs_boundary_fails_below_minimum(validator, count):
    output = mock_unit_test_generator_output()
    output.backend_unit_test_specifications = [
        UnitTestSpecification(
            id=f"BE-UT-{i}",
            name=f"BE {i}",
            description=f"Backend test {i}",
            target_module=f"service_{i}.py",
            test_type="unit",
            assertions=["assert 1"],
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("backend_specs" in err for err in result.errors)


@pytest.mark.parametrize("count", [5, 6, 9])
def test_backend_specs_boundary_passes_at_minimum(validator, count):
    output = mock_unit_test_generator_output()
    output.backend_unit_test_specifications = [
        UnitTestSpecification(
            id=f"BE-UT-{i}",
            name=f"BE {i}",
            description=f"Backend test {i}",
            target_module=f"service_{i}.py",
            test_type="unit",
            assertions=["assert 1"],
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert "backend_specs" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 2])
def test_fixtures_boundary_fails_below_minimum(validator, count):
    output = mock_unit_test_generator_output()
    output.test_fixtures = [
        TestFixture(
            id=f"FIX-{i}",
            name=f"Fixture {i}",
            description=f"Fixture {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("test_fixtures" in err for err in result.errors)


@pytest.mark.parametrize("count", [3, 4, 6])
def test_fixtures_boundary_passes_at_minimum(validator, count):
    output = mock_unit_test_generator_output()
    output.test_fixtures = [
        TestFixture(
            id=f"FIX-{i}",
            name=f"Fixture {i}",
            description=f"Fixture {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert "test_fixtures" not in " ".join(result.errors)


@pytest.mark.parametrize("mock_strategy", [{}, None])
def test_mock_strategy_required(validator, mock_strategy):
    output = mock_unit_test_generator_output(
        mock_strategy={} if mock_strategy is None else mock_strategy
    )
    if mock_strategy is None:
        output = UnitTestGeneratorOutput(**(output.model_dump() | {"mock_strategy": {}}))
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("mock_strategy" in err for err in result.errors)


@pytest.mark.parametrize("coverage_targets", [{}, None])
def test_coverage_targets_required(validator, coverage_targets):
    output = mock_unit_test_generator_output(
        coverage_targets={} if coverage_targets is None else coverage_targets
    )
    if coverage_targets is None:
        output = UnitTestGeneratorOutput(**(output.model_dump() | {"coverage_targets": {}}))
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("coverage_targets" in err for err in result.errors)
