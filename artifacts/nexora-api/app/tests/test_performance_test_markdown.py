from app.performance_test.markdown import output_to_markdown
from app.tests.conftest import mock_performance_test_output


def test_markdown_includes_title():
    md = output_to_markdown(mock_performance_test_output())
    assert "# Performance Test Plan" in md


def test_markdown_includes_section_1():
    md = output_to_markdown(mock_performance_test_output())
    assert "## Load Test Plan" in md


def test_markdown_includes_section_2():
    md = output_to_markdown(mock_performance_test_output())
    assert "## Stress Test Plan" in md


def test_markdown_includes_section_3():
    md = output_to_markdown(mock_performance_test_output())
    assert "## Performance Bottlenecks" in md


def test_markdown_includes_section_4():
    md = output_to_markdown(mock_performance_test_output())
    assert "## Scaling Recommendations" in md


def test_markdown_includes_section_5():
    md = output_to_markdown(mock_performance_test_output())
    assert "## Caching Recommendations" in md
