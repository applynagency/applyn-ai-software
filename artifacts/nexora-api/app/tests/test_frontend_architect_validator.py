from app.frontend_architect.validator import FrontendArchitectValidator
from app.schemas.frontend_architect import FrontendArchitectOutput
from app.tests.conftest import mock_frontend_architect_output


def test_validator_accepts_complete_output():
    validator = FrontendArchitectValidator()
    result = validator.validate(mock_frontend_architect_output())
    assert result.is_valid is True
    assert result.score >= 80


def test_validator_rejects_insufficient_pages():
    validator = FrontendArchitectValidator()
    output = mock_frontend_architect_output()
    data = output.model_dump()
    data["page_architecture"] = data["page_architecture"][:2]
    result = validator.validate(FrontendArchitectOutput(**data))
    assert result.is_valid is False
    assert any("page_architecture" in error for error in result.errors)


def test_validator_rejects_insufficient_routes():
    validator = FrontendArchitectValidator()
    output = mock_frontend_architect_output()
    data = output.model_dump()
    data["routing_architecture"] = data["routing_architecture"][:2]
    result = validator.validate(FrontendArchitectOutput(**data))
    assert result.is_valid is False
    assert any("routing_architecture" in error for error in result.errors)


def test_validator_rejects_insufficient_components():
    validator = FrontendArchitectValidator()
    output = mock_frontend_architect_output()
    data = output.model_dump()
    data["component_architecture"] = data["component_architecture"][:5]
    result = validator.validate(FrontendArchitectOutput(**data))
    assert result.is_valid is False
    assert any("component_architecture" in error for error in result.errors)


def test_validator_rejects_insufficient_forms():
    validator = FrontendArchitectValidator()
    output = mock_frontend_architect_output()
    data = output.model_dump()
    data["forms"] = data["forms"][:1]
    result = validator.validate(FrontendArchitectOutput(**data))
    assert result.is_valid is False
    assert any("forms" in error for error in result.errors)


def test_validator_rejects_insufficient_api_integrations():
    validator = FrontendArchitectValidator()
    output = mock_frontend_architect_output()
    data = output.model_dump()
    data["api_integration"] = {"integrations": data["api_integration"]["integrations"][:1]}
    result = validator.validate(FrontendArchitectOutput(**data))
    assert result.is_valid is False
    assert any("api_integrations" in error for error in result.errors)


def test_validator_counts_are_reported():
    validator = FrontendArchitectValidator()
    result = validator.validate(mock_frontend_architect_output())
    assert result.counts["page_architecture"] >= 10
    assert result.counts["component_architecture"] >= 20
    assert result.counts["forms"] >= 5
    assert result.counts["routing_architecture"] >= 10
    assert result.counts["api_integrations"] >= 5


def test_validator_score_is_rounded():
    validator = FrontendArchitectValidator()
    result = validator.validate(mock_frontend_architect_output())
    assert result.score == round(result.score, 2)


def test_validator_empty_output_fails():
    validator = FrontendArchitectValidator()
    result = validator.validate(FrontendArchitectOutput())
    assert result.is_valid is False
    assert len(result.errors) == 5


def test_validator_bonus_for_optional_sections():
    validator = FrontendArchitectValidator()
    base = mock_frontend_architect_output()
    minimal = FrontendArchitectOutput(
        routing_architecture=base.routing_architecture,
        page_architecture=base.page_architecture,
        component_architecture=base.component_architecture,
        forms=base.forms,
        api_integration=base.api_integration,
    )
    full = mock_frontend_architect_output()
    minimal_result = validator.validate(minimal)
    full_result = validator.validate(full)
    assert full_result.score >= minimal_result.score
