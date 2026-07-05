from app.tests.conftest import mock_unit_test_generator_output
from app.unit_test_generator.markdown import output_to_markdown


def test_markdown_includes_title():
    md = output_to_markdown(mock_unit_test_generator_output())
    assert "# Unit Test Specifications" in md


def test_markdown_includes_frontend_unit_tests():
    md = output_to_markdown(mock_unit_test_generator_output())
    assert "## Frontend Unit Tests" in md


def test_markdown_includes_backend_unit_tests():
    md = output_to_markdown(mock_unit_test_generator_output())
    assert "## Backend Unit Tests" in md


def test_markdown_includes_test_fixtures():
    md = output_to_markdown(mock_unit_test_generator_output())
    assert "## Test Fixtures" in md


def test_markdown_includes_coverage_targets():
    md = output_to_markdown(mock_unit_test_generator_output())
    assert "## Coverage Targets" in md
