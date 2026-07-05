from app.sre_approval.markdown import output_to_markdown
from app.tests.conftest import mock_sre_approval_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_sre_approval_output())
    assert "# SRE Production Readiness Decision" in md


def test_markdown_includes_sre_status():
    md = output_to_markdown(mock_sre_approval_output())
    assert "SRE Status:" in md


def test_markdown_includes_all_scores():
    md = output_to_markdown(mock_sre_approval_output())
    assert "Production Readiness Score:" in md
    assert "Availability Score:" in md
    assert "Security Score:" in md
    assert "Performance Score:" in md
    assert "Cost Score:" in md
    assert "Operational Readiness Score:" in md


def test_markdown_includes_findings():
    md = output_to_markdown(mock_sre_approval_output())
    assert "## Findings" in md


def test_markdown_includes_recommendation():
    md = output_to_markdown(mock_sre_approval_output())
    assert "## Recommendation" in md


def test_markdown_includes_warnings_when_present():
    md = output_to_markdown(mock_sre_approval_output(warnings=["watch costs"]))
    assert "## Warnings" in md
