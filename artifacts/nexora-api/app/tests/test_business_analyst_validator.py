import pytest

from app.business_analyst.validator import BusinessAnalystValidator
from app.tests.conftest import mock_business_analyst_output


@pytest.fixture
def validator():
    return BusinessAnalystValidator()


def test_valid_output_passes(validator):
    result = validator.validate(mock_business_analyst_output())
    assert result.is_valid is True
    assert result.score >= 80
    assert not result.errors


def test_insufficient_functional_requirements(validator):
    output = mock_business_analyst_output()
    output.functional_requirements = output.functional_requirements[:2]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("functional_requirements" in err for err in result.errors)


def test_insufficient_modules(validator):
    output = mock_business_analyst_output()
    output.modules = output.modules[:1]
    result = validator.validate(output)
    assert result.is_valid is False
    assert any("modules" in err for err in result.errors)


def test_insufficient_roles(validator):
    output = mock_business_analyst_output()
    output.roles = output.roles[:1]
    result = validator.validate(output)
    assert result.is_valid is False


def test_insufficient_user_flows(validator):
    output = mock_business_analyst_output()
    output.user_flows = output.user_flows[:1]
    result = validator.validate(output)
    assert result.is_valid is False


def test_insufficient_business_rules(validator):
    output = mock_business_analyst_output()
    output.business_rules = output.business_rules[:1]
    result = validator.validate(output)
    assert result.is_valid is False


def test_insufficient_acceptance_criteria(validator):
    output = mock_business_analyst_output()
    output.acceptance_criteria = output.acceptance_criteria[:1]
    result = validator.validate(output)
    assert result.is_valid is False


def test_validation_score_present(validator):
    result = validator.validate(mock_business_analyst_output())
    assert 0 <= result.score <= 100


def test_validation_counts_reported(validator):
    result = validator.validate(mock_business_analyst_output())
    assert result.counts["functional_requirements"] == 5
    assert result.counts["modules"] == 3


def test_empty_output_fails(validator):
    from app.schemas.business_analyst import BusinessAnalystOutput

    result = validator.validate(BusinessAnalystOutput())
    assert result.is_valid is False
    assert len(result.errors) == 6


def test_partial_output_score_below_full(validator):
    output = mock_business_analyst_output()
    output.functional_requirements = output.functional_requirements[:3]
    result = validator.validate(output)
    assert result.score < 100


def test_bonus_fields_increase_score(validator):
    from app.schemas.business_analyst import NonFunctionalRequirement, PermissionDefinition

    base = mock_business_analyst_output()
    base_score = validator.validate(base).score
    base.non_functional_requirements = [
        NonFunctionalRequirement(id="NFR-1", category="security", description="Secure")
    ]
    base.permissions = [
        PermissionDefinition(
            id="P-1", role="Admin", resource="data", action="read", description="Read"
        )
    ]
    boosted = validator.validate(base).score
    assert boosted >= base_score
