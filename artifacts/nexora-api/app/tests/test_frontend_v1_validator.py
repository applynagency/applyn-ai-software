from app.frontend_v1.validator import FrontendDeveloperV1Validator
from app.schemas.frontend_v1 import FrontendDeveloperV1Output
from app.tests.conftest import mock_frontend_v1_output


def test_validator_accepts_complete_output():
    validator = FrontendDeveloperV1Validator()
    result = validator.validate(mock_frontend_v1_output())
    assert result.is_valid is True
    assert result.score >= 80


def test_validator_rejects_insufficient_pages():
    validator = FrontendDeveloperV1Validator()
    output = mock_frontend_v1_output()
    data = output.model_dump()
    data["page_structure"] = data["page_structure"][:3]
    result = validator.validate(FrontendDeveloperV1Output(**data))
    assert result.is_valid is False
    assert any("page_structure" in error for error in result.errors)


def test_validator_rejects_insufficient_components():
    validator = FrontendDeveloperV1Validator()
    output = mock_frontend_v1_output()
    data = output.model_dump()
    data["component_structure"] = data["component_structure"][:5]
    result = validator.validate(FrontendDeveloperV1Output(**data))
    assert result.is_valid is False
    assert any("component_structure" in error for error in result.errors)


def test_validator_rejects_insufficient_forms():
    validator = FrontendDeveloperV1Validator()
    output = mock_frontend_v1_output()
    data = output.model_dump()
    data["form_architecture"] = data["form_architecture"][:2]
    result = validator.validate(FrontendDeveloperV1Output(**data))
    assert result.is_valid is False
    assert any("form_architecture" in error for error in result.errors)


def test_validator_rejects_insufficient_routes():
    validator = FrontendDeveloperV1Validator()
    output = mock_frontend_v1_output()
    data = output.model_dump()
    data["route_structure"] = data["route_structure"][:3]
    result = validator.validate(FrontendDeveloperV1Output(**data))
    assert result.is_valid is False
    assert any("route_structure" in error for error in result.errors)


def test_validator_rejects_insufficient_state_modules():
    validator = FrontendDeveloperV1Validator()
    output = mock_frontend_v1_output()
    data = output.model_dump()
    data["state_management"] = {"modules": data["state_management"]["modules"][:2]}
    result = validator.validate(FrontendDeveloperV1Output(**data))
    assert result.is_valid is False
    assert any("state_modules" in error for error in result.errors)


def test_validator_counts_are_reported():
    validator = FrontendDeveloperV1Validator()
    result = validator.validate(mock_frontend_v1_output())
    assert result.counts["page_structure"] >= 10
    assert result.counts["component_structure"] >= 20
    assert result.counts["state_modules"] >= 5


def test_validator_score_is_rounded():
    validator = FrontendDeveloperV1Validator()
    result = validator.validate(mock_frontend_v1_output())
    assert result.score == round(result.score, 2)


def test_validator_empty_output_fails():
    validator = FrontendDeveloperV1Validator()
    result = validator.validate(FrontendDeveloperV1Output())
    assert result.is_valid is False
    assert len(result.errors) == 5


def test_validator_bonus_for_optional_sections():
    validator = FrontendDeveloperV1Validator()
    base = mock_frontend_v1_output()
    minimal = FrontendDeveloperV1Output(
        route_structure=base.route_structure,
        page_structure=base.page_structure,
        component_structure=base.component_structure,
        form_architecture=base.form_architecture,
        state_management=base.state_management,
    )
    full = mock_frontend_v1_output()
    minimal_result = validator.validate(minimal)
    full_result = validator.validate(full)
    assert full_result.score >= minimal_result.score
