from app.frontend_v2.validator import FrontendDeveloperV2Validator
from app.schemas.frontend_v2 import FrontendDeveloperV2Output
from app.tests.conftest import mock_frontend_v2_output


def test_validator_accepts_complete_output():
    validator = FrontendDeveloperV2Validator()
    result = validator.validate(mock_frontend_v2_output())
    assert result.is_valid is True
    assert result.score >= 80


def test_validator_rejects_insufficient_pages():
    validator = FrontendDeveloperV2Validator()
    output = mock_frontend_v2_output()
    data = output.model_dump()
    data["page_files"] = data["page_files"][:3]
    result = validator.validate(FrontendDeveloperV2Output(**data))
    assert result.is_valid is False
    assert any("page_files" in error for error in result.errors)


def test_validator_rejects_insufficient_components():
    validator = FrontendDeveloperV2Validator()
    output = mock_frontend_v2_output()
    data = output.model_dump()
    data["component_files"] = data["component_files"][:5]
    result = validator.validate(FrontendDeveloperV2Output(**data))
    assert result.is_valid is False
    assert any("component_files" in error for error in result.errors)


def test_validator_rejects_insufficient_services():
    validator = FrontendDeveloperV2Validator()
    output = mock_frontend_v2_output()
    data = output.model_dump()
    data["service_files"] = data["service_files"][:2]
    result = validator.validate(FrontendDeveloperV2Output(**data))
    assert result.is_valid is False
    assert any("service_files" in error for error in result.errors)


def test_validator_rejects_insufficient_stores():
    validator = FrontendDeveloperV2Validator()
    output = mock_frontend_v2_output()
    data = output.model_dump()
    data["store_files"] = data["store_files"][:2]
    result = validator.validate(FrontendDeveloperV2Output(**data))
    assert result.is_valid is False
    assert any("store_files" in error for error in result.errors)


def test_validator_rejects_insufficient_hooks():
    validator = FrontendDeveloperV2Validator()
    output = mock_frontend_v2_output()
    data = output.model_dump()
    data["hook_files"] = data["hook_files"][:2]
    result = validator.validate(FrontendDeveloperV2Output(**data))
    assert result.is_valid is False
    assert any("hook_files" in error for error in result.errors)


def test_validator_counts_are_reported():
    validator = FrontendDeveloperV2Validator()
    result = validator.validate(mock_frontend_v2_output())
    assert result.counts["page_files"] >= 10
    assert result.counts["component_files"] >= 20
    assert result.counts["store_files"] >= 5


def test_validator_score_is_rounded():
    validator = FrontendDeveloperV2Validator()
    result = validator.validate(mock_frontend_v2_output())
    assert result.score == round(result.score, 2)


def test_validator_empty_output_fails():
    validator = FrontendDeveloperV2Validator()
    result = validator.validate(FrontendDeveloperV2Output())
    assert result.is_valid is False
    assert len(result.errors) == 8


def test_validator_bonus_for_optional_sections():
    validator = FrontendDeveloperV2Validator()
    base = mock_frontend_v2_output()
    minimal = FrontendDeveloperV2Output(
        page_files=base.page_files,
        component_files=base.component_files,
        service_files=base.service_files,
        store_files=base.store_files,
        hook_files=base.hook_files,
        provider_files=base.provider_files,
        type_files=base.type_files,
    )
    full = mock_frontend_v2_output()
    minimal_result = validator.validate(minimal)
    full_result = validator.validate(full)
    assert full_result.score >= minimal_result.score
