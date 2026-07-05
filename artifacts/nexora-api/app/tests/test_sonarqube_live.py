"""Unit tests for SonarQube live security scan."""

from __future__ import annotations

from unittest.mock import patch

from app.security_platform.providers.sonarqube_live import scan_project


def test_scan_project_missing_credentials():
    result = scan_project({}, project_key="my-app")
    assert result["simulated"] is True
    assert result["unavailable_reason"] == "missing_endpoint_or_token"


@patch("app.security_platform.providers.sonarqube_live.get_json")
def test_scan_project_parses_issues(mock_get_json):
    mock_get_json.return_value = {
        "issues": [
            {
                "severity": "CRITICAL",
                "message": "SQL injection risk",
                "rule": "java:S3649",
                "component": "src/main/App.java",
                "type": "VULNERABILITY",
            }
        ]
    }
    result = scan_project(
        {"endpoint": "http://sonar:9000", "token": "tok"},
        project_key="my-app",
    )
    assert result["simulated"] is False
    assert result["summary"]["total"] == 1
    assert result["findings"][0]["severity"] == "CRITICAL"
