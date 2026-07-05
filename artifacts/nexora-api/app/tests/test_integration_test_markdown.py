from app.integration_test.markdown import output_to_markdown
from app.tests.conftest import mock_integration_test_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_integration_test_output())
    assert "# Integration Test Plan" in md


def test_markdown_includes_section_1():
    md = output_to_markdown(mock_integration_test_output())
    assert "## API Test Cases" in md


def test_markdown_includes_section_2():
    md = output_to_markdown(mock_integration_test_output())
    assert "## Frontend/Backend Flows" in md


def test_markdown_includes_section_3():
    md = output_to_markdown(mock_integration_test_output())
    assert "## Database Validation" in md


def test_markdown_includes_section_4():
    md = output_to_markdown(mock_integration_test_output())
    assert "## Integration Coverage" in md
