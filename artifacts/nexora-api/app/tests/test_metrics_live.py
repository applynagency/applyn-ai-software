"""Unit tests for live metrics providers."""

from __future__ import annotations

from unittest.mock import patch

from app.observability_platform.providers.metrics_live import (
    discover_prometheus,
    query_prometheus,
)


def test_query_prometheus_missing_endpoint():
    result = query_prometheus({}, "up")
    assert result["provider"] == "PROMETHEUS"
    assert result["simulated"] is True
    assert result["unavailable_reason"] == "missing_endpoint"


@patch("app.observability_platform.providers.metrics_live.get_json")
def test_query_prometheus_parses_series(mock_get_json):
    mock_get_json.return_value = {
        "data": {
            "result": [
                {
                    "metric": {"__name__": "up", "job": "api"},
                    "values": [[1700000000, "1"], [1700003600, "1"]],
                }
            ]
        }
    }
    result = query_prometheus({"endpoint": "http://prom:9090"}, "up", window="1h")
    assert result["simulated"] is False
    assert result["total"] == 1
    assert result["series"][0]["metric"]["job"] == "api"


@patch("app.observability_platform.providers.metrics_live.get_json")
def test_discover_prometheus(mock_get_json):
    mock_get_json.return_value = {"data": ["up", "http_requests_total"]}
    names = discover_prometheus({"endpoint": "http://prom:9090"})
    assert len(names) == 2
    assert names[0]["name"] == "up"
