from app.security_test.markdown import output_to_markdown
from app.tests.conftest import mock_security_test_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_security_test_output())
    assert "# Security Test Assessment" in md


def test_markdown_includes_section_1():
    md = output_to_markdown(mock_security_test_output())
    assert "## OWASP Assessment" in md


def test_markdown_includes_section_2():
    md = output_to_markdown(mock_security_test_output())
    assert "## Authentication Review" in md


def test_markdown_includes_section_3():
    md = output_to_markdown(mock_security_test_output())
    assert "## Authorization Review" in md


def test_markdown_includes_section_4():
    md = output_to_markdown(mock_security_test_output())
    assert "## Input Validation Review" in md


def test_markdown_includes_section_5():
    md = output_to_markdown(mock_security_test_output())
    assert "## Dependency Security Scan" in md


def test_markdown_includes_section_6():
    md = output_to_markdown(mock_security_test_output())
    assert "## Secrets Exposure Review" in md
