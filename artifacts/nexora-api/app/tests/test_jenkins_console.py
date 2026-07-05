"""Tests for Jenkins console excerpt helper."""

from app.delivery.pipelines.jenkins_live import fetch_build_console_excerpt


def test_fetch_build_console_excerpt_missing_creds():
    result = fetch_build_console_excerpt({}, "build", 3)
    assert result["available"] is False
