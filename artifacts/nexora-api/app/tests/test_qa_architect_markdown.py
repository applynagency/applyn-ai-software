from app.qa_architect.markdown import output_to_markdown
from app.tests.conftest import mock_qa_architect_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_qa_architect_output())
    assert "# QA Architecture Blueprint" in md


def test_markdown_includes_test_strategy():
    md = output_to_markdown(mock_qa_architect_output())
    assert "## Test Strategy" in md


def test_markdown_includes_coverage_matrix():
    md = output_to_markdown(mock_qa_architect_output())
    assert "## Test Coverage Matrix" in md


def test_markdown_includes_risk_areas():
    md = output_to_markdown(mock_qa_architect_output())
    assert "## Risk Areas" in md


def test_markdown_includes_acceptance_plan():
    md = output_to_markdown(mock_qa_architect_output())
    assert "## Acceptance Test Plan" in md
