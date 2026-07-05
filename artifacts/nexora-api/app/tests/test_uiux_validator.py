from app.schemas.uiux_designer import UIUXDesignerOutput
from app.tests.conftest import mock_uiux_designer_output
from app.uiux_designer.validator import UIUXValidator


def test_validator_accepts_complete_output():
    validator = UIUXValidator()
    result = validator.validate(mock_uiux_designer_output())
    assert result.is_valid is True
    assert result.score >= 80


def test_validator_rejects_insufficient_screens():
    validator = UIUXValidator()
    output = mock_uiux_designer_output()
    data = output.model_dump()
    data["screen_inventory"] = data["screen_inventory"][:2]
    result = validator.validate(UIUXDesignerOutput(**data))
    assert result.is_valid is False
    assert any("screen_inventory" in error for error in result.errors)


def test_validator_rejects_insufficient_user_flows():
    validator = UIUXValidator()
    output = mock_uiux_designer_output()
    data = output.model_dump()
    data["user_flows"] = data["user_flows"][:1]
    result = validator.validate(UIUXDesignerOutput(**data))
    assert result.is_valid is False
    assert any("user_flows" in error for error in result.errors)


def test_validator_rejects_insufficient_components():
    validator = UIUXValidator()
    output = mock_uiux_designer_output()
    data = output.model_dump()
    data["component_inventory"] = data["component_inventory"][:2]
    result = validator.validate(UIUXDesignerOutput(**data))
    assert result.is_valid is False
    assert any("component_inventory" in error for error in result.errors)


def test_validator_rejects_insufficient_navigation_groups():
    validator = UIUXValidator()
    output = mock_uiux_designer_output()
    data = output.model_dump()
    data["navigation_structure"] = data["navigation_structure"][:1]
    result = validator.validate(UIUXDesignerOutput(**data))
    assert result.is_valid is False
    assert any("navigation_structure" in error for error in result.errors)


def test_validator_rejects_insufficient_roles():
    validator = UIUXValidator()
    output = mock_uiux_designer_output()
    data = output.model_dump()
    data["role_screen_mapping"] = data["role_screen_mapping"][:1]
    result = validator.validate(UIUXDesignerOutput(**data))
    assert result.is_valid is False
    assert any("role_screen_mapping" in error for error in result.errors)


def test_validator_counts_are_reported():
    validator = UIUXValidator()
    result = validator.validate(mock_uiux_designer_output())
    assert result.counts["screen_inventory"] >= 5
    assert result.counts["user_flows"] >= 3
    assert result.counts["component_inventory"] >= 5


def test_validator_score_is_rounded():
    validator = UIUXValidator()
    result = validator.validate(mock_uiux_designer_output())
    assert result.score == round(result.score, 2)


def test_validator_empty_output_fails():
    validator = UIUXValidator()
    result = validator.validate(UIUXDesignerOutput())
    assert result.is_valid is False
    assert len(result.errors) == 5


def test_validator_bonus_for_optional_sections():
    validator = UIUXValidator()
    base = mock_uiux_designer_output()
    minimal = UIUXDesignerOutput(
        navigation_structure=base.navigation_structure,
        user_flows=base.user_flows,
        screen_inventory=base.screen_inventory,
        role_screen_mapping=base.role_screen_mapping,
        component_inventory=base.component_inventory,
    )
    full = mock_uiux_designer_output()
    minimal_result = validator.validate(minimal)
    full_result = validator.validate(full)
    assert full_result.score >= minimal_result.score
