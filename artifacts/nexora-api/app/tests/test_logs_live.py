"""Unit tests for live log search providers."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from app.observability_platform.providers.logs_live import (
    search_cloudwatch,
    search_elastic,
    search_loki,
)


def test_search_loki_missing_endpoint():
    result = search_loki({}, query="error")
    assert result["provider"] == "LOKI"
    assert result["simulated"] is True
    assert result["unavailable_reason"] == "missing_endpoint"
    assert result["lines"] == []


@patch("app.observability_platform.providers.logs_live.get_json")
def test_search_loki_parses_streams(mock_get_json):
    mock_get_json.return_value = {
        "data": {
            "result": [
                {
                    "stream": {"job": "api"},
                    "values": [["1700000000000000000", "connection refused"]],
                }
            ]
        }
    }
    result = search_loki({"endpoint": "http://loki:3100"}, query="refused", limit=10)
    assert result["simulated"] is False
    assert result["total"] == 1
    assert result["lines"][0]["line"] == "connection refused"
    assert result["lines"][0]["labels"]["job"] == "api"


def test_search_elastic_missing_credentials():
    result = search_elastic({"endpoint": "http://es:9200"}, query="error")
    assert result["provider"] == "ELASTIC"
    assert result["unavailable_reason"] == "missing_endpoint_or_api_key"


@patch("app.observability_platform.providers.logs_live._post_json")
def test_search_elastic_parses_hits(mock_post):
    mock_post.return_value = {
        "hits": {
            "hits": [
                {
                    "_index": "logs-2026",
                    "_id": "1",
                    "_source": {"@timestamp": "2026-01-01T00:00:00Z", "message": "disk full"},
                }
            ]
        }
    }
    result = search_elastic(
        {"endpoint": "http://es:9200", "api_key": "abc"},
        query="disk",
        limit=5,
    )
    assert result["simulated"] is False
    assert result["total"] == 1
    assert result["lines"][0]["line"] == "disk full"


def test_search_cloudwatch_missing_credentials():
    result = search_cloudwatch({}, query="error")
    assert result["provider"] == "CLOUDWATCH"
    assert result["unavailable_reason"] == "missing_aws_credentials"


@patch("app.observability_platform.providers.logs_live.get_json")
def test_search_loki_http_error(mock_get_json):
    mock_get_json.side_effect = RuntimeError("HTTP 503: unavailable")
    result = search_loki({"endpoint": "http://loki:3100"}, query="error")
    assert result["simulated"] is False
    assert result.get("error") is True
    assert "503" in (result.get("unavailable_reason") or "")


def test_search_cloudwatch_parses_events():
    client = MagicMock()
    client.filter_log_events.return_value = {
        "events": [
            {"timestamp": 1700000000000, "message": "oom killed", "logStreamName": "pod-1"},
        ]
    }
    mock_boto3 = MagicMock()
    mock_boto3.client.return_value = client
    mock_botocore = MagicMock()
    mock_botocore.exceptions.BotoCoreError = Exception
    mock_botocore.exceptions.ClientError = Exception
    modules = {
        "boto3": mock_boto3,
        "botocore": mock_botocore,
        "botocore.exceptions": mock_botocore.exceptions,
    }
    with patch.dict(sys.modules, modules):
        result = search_cloudwatch(
            {
                "access_key": "AKIA",
                "secret_key": "secret",
                "region": "us-west-2",
                "log_group": "/ecs/api",
            },
            query="oom",
            limit=10,
        )
    assert result["simulated"] is False
    assert result["total"] == 1
    assert result["lines"][0]["line"] == "oom killed"
    client.filter_log_events.assert_called_once()
