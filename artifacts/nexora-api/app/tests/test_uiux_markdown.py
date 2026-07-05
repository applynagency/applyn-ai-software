from app.tests.conftest import mock_uiux_designer_output
from app.uiux_designer.markdown import output_to_markdown


def test_markdown_includes_title():
    md = output_to_markdown(mock_uiux_designer_output())
    assert "# UI/UX Design Specification" in md


def test_markdown_includes_information_architecture():
    md = output_to_markdown(mock_uiux_designer_output())
    assert "## Information Architecture" in md


def test_markdown_includes_navigation_structure():
    md = output_to_markdown(mock_uiux_designer_output())
    assert "## Navigation Structure" in md


def test_markdown_includes_screen_inventory():
    md = output_to_markdown(mock_uiux_designer_output())
    assert "## Screen Inventory" in md


def test_markdown_includes_user_flows():
    md = output_to_markdown(mock_uiux_designer_output())
    assert "## User Flows" in md


def test_markdown_includes_component_inventory():
    md = output_to_markdown(mock_uiux_designer_output())
    assert "## Component Inventory" in md


def test_markdown_includes_frontend_handoff():
    md = output_to_markdown(mock_uiux_designer_output())
    assert "## Frontend Handoff Specification" in md


def test_markdown_includes_accessibility_guidelines():
    md = output_to_markdown(mock_uiux_designer_output())
    assert "## Accessibility Guidelines" in md
