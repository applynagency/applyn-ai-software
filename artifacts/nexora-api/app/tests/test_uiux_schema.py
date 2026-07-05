from app.schemas.uiux_designer import UIUXDesignerOutput
from app.tests.conftest import mock_uiux_designer_output


def test_output_schema_defaults():
    output = UIUXDesignerOutput()
    assert output.information_architecture == {}
    assert output.navigation_structure == []
    assert output.frontend_handoff == {}


def test_mock_output_is_valid_schema():
    output = mock_uiux_designer_output()
    assert isinstance(output, UIUXDesignerOutput)
    dumped = output.model_dump()
    assert len(dumped["screen_inventory"]) >= 5


def test_output_serializes_navigation_groups():
    output = mock_uiux_designer_output()
    groups = output.model_dump()["navigation_structure"]
    assert all("name" in group and "items" in group for group in groups)


def test_output_serializes_role_mappings():
    output = mock_uiux_designer_output()
    roles = output.model_dump()["role_screen_mapping"]
    assert len(roles) >= 2
    assert all("role" in role and "screens" in role for role in roles)


def test_output_serializes_components():
    output = mock_uiux_designer_output()
    components = output.model_dump()["component_inventory"]
    assert all("category" in component for component in components)
