from app.qa_approval.markdown import output_to_markdown
from app.tests.conftest import mock_qa_approval_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_qa_approval_output())
    assert "# QA Approval Decision" in md


def test_markdown_includes_section_1():
    md = output_to_markdown(mock_qa_approval_output())
    assert "## Findings" in md


def test_markdown_includes_section_2():
    md = output_to_markdown(mock_qa_approval_output())
    assert "## Warnings" in md


def test_markdown_includes_section_3():
    md = output_to_markdown(mock_qa_approval_output())
    assert "## Recommendation" in md
