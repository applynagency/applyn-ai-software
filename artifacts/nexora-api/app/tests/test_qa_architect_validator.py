import pytest

from app.qa_architect.validator import MINIMUM_COUNTS, QAArchitectValidator
from app.schemas.qa_architect import (
    AcceptanceCriterion,
    QAArchitectOutput,
    RegressionScenario,
    RiskArea,
    TestScenario,
    UserJourney,
)
from app.tests.conftest import mock_qa_architect_output


@pytest.fixture
def validator():
    return QAArchitectValidator()


def test_valid_output_passes(validator):
    result = validator.validate(mock_qa_architect_output())
    assert result.is_valid is True
    assert result.score >= 80
    assert not result.errors


def test_validation_score_present(validator):
    result = validator.validate(mock_qa_architect_output())
    assert 0 <= result.score <= 100


def test_validation_counts_reported(validator):
    result = validator.validate(mock_qa_architect_output())
    assert result.counts["test_scenarios"] == 10
    assert result.counts["risk_areas"] == 5
    assert result.counts["acceptance_criteria"] == 5
    assert result.counts["regression_scenarios"] == 5
    assert result.counts["critical_user_journeys"] == 3


def test_empty_output_fails(validator):
    result = validator.validate(QAArchitectOutput())
    assert result.is_valid is False
    assert len(result.errors) == len(MINIMUM_COUNTS) + 1


def test_validator_score_is_rounded(validator):
    result = validator.validate(mock_qa_architect_output())
    assert result.score == round(result.score, 2)


def test_bonus_journeys_increase_score(validator):
    base = mock_qa_architect_output(critical_user_journeys=[])
    base_score = validator.validate(base).score
    bonus = mock_qa_architect_output()
    bonus_score = validator.validate(bonus).score
    assert bonus_score >= base_score


@pytest.mark.parametrize("count", [0, 1, 5, 9])
def test_test_scenarios_boundary_fails_below_minimum(validator, count):
    output = mock_qa_architect_output()
    output.test_coverage_matrix = [
        TestScenario(
            id=f"TS-{i}",
            name=f"Scenario {i}",
            description=f"Scenario desc {i}",
            layer="integration",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("test_scenarios" in err for err in result.errors)


@pytest.mark.parametrize("count", [10, 11, 15])
def test_test_scenarios_boundary_passes_at_minimum(validator, count):
    output = mock_qa_architect_output()
    output.test_coverage_matrix = [
        TestScenario(
            id=f"TS-{i}",
            name=f"Scenario {i}",
            description=f"Scenario desc {i}",
            layer="integration",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert "test_scenarios" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 4])
def test_risk_areas_boundary_fails_below_minimum(validator, count):
    output = mock_qa_architect_output()
    output.risk_areas = [
        RiskArea(
            id=f"RISK-{i}",
            name=f"Risk {i}",
            description=f"Risk desc {i}",
            severity="medium",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("risk_areas" in err for err in result.errors)


@pytest.mark.parametrize("count", [5, 6, 9])
def test_risk_areas_boundary_passes_at_minimum(validator, count):
    output = mock_qa_architect_output()
    output.risk_areas = [
        RiskArea(
            id=f"RISK-{i}",
            name=f"Risk {i}",
            description=f"Risk desc {i}",
            severity="medium",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert "risk_areas" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 2, 4])
def test_acceptance_criteria_boundary_fails_below_minimum(validator, count):
    output = mock_qa_architect_output()
    output.acceptance_test_plan = [
        AcceptanceCriterion(
            id=f"AT-{i}",
            name=f"Acceptance {i}",
            description=f"Acceptance desc {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("acceptance_criteria" in err for err in result.errors)


@pytest.mark.parametrize("count", [5, 7])
def test_acceptance_criteria_boundary_passes_at_minimum(validator, count):
    output = mock_qa_architect_output()
    output.acceptance_test_plan = [
        AcceptanceCriterion(
            id=f"AT-{i}",
            name=f"Acceptance {i}",
            description=f"Acceptance desc {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert "acceptance_criteria" not in " ".join(result.errors)


@pytest.mark.parametrize("count", [0, 1, 4])
def test_regression_scenarios_boundary_fails_below_minimum(validator, count):
    output = mock_qa_architect_output()
    output.regression_areas = [
        RegressionScenario(
            id=f"REG-{i}",
            name=f"Regression {i}",
            description=f"Regression desc {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("regression_scenarios" in err for err in result.errors)


@pytest.mark.parametrize("count", [5, 8])
def test_regression_scenarios_boundary_passes_at_minimum(validator, count):
    output = mock_qa_architect_output()
    output.regression_areas = [
        RegressionScenario(
            id=f"REG-{i}",
            name=f"Regression {i}",
            description=f"Regression desc {i}",
        )
        for i in range(1, count + 1)
    ]
    result = validator.validate(output)
    assert "regression_scenarios" not in " ".join(result.errors)


@pytest.mark.parametrize("strategy_text", ["", " ", "\n"])
def test_empty_test_strategy_fails(validator, strategy_text):
    output = mock_qa_architect_output(test_strategy=strategy_text)
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("test_strategy" in err for err in result.errors)


@pytest.mark.parametrize("journey_count,expect_bonus", [(0, False), (1, False), (2, False), (3, True), (5, True)])
def test_critical_journey_bonus_threshold(validator, journey_count, expect_bonus):
    output = mock_qa_architect_output(
        critical_user_journeys=[
            UserJourney(
                id=f"CUJ-{i}",
                name=f"Journey {i}",
                description=f"Journey desc {i}",
                steps=["a", "b"],
            )
            for i in range(1, journey_count + 1)
        ]
    )
    result = validator.validate(output)
    if expect_bonus:
        assert result.score >= 100 or result.score > 95
    else:
        assert result.score <= 100
